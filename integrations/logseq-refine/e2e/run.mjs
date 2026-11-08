#!/usr/bin/env node
// End-to-end check of the plugin in a throwaway Logseq (sandbox.mjs) against a test voice typing (server.py).
//
//   uv run python e2e/server.py --root ../../.run/logseq-test --key KEY --port 8791 [--model gateway]   (keep running)
//   node e2e/run.mjs --key KEY [--server-port 8791] [--mode fake|gateway] [--root DIR]
//
// It resets the sandbox's profile and graph (keeping the copied app), loads this plugin with its settings, makes a
// page of test blocks, and drives the plugin the way you would: right-click on a block's bullet, then a menu item.
// fake mode checks exact results against server.py's table; gateway mode refines one block with the real local model
// and checks that the links survive and the log holds the entry. Prints PASS/FAIL lines; exits 1 on any FAIL.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const args = process.argv.slice(2);
const opt = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i < 0 ? fallback : args[i + 1];
};
const here = path.dirname(fileURLToPath(import.meta.url));
const plugin = path.resolve(here, "..");
const repo = path.resolve(plugin, "..", "..");
const root = path.resolve(opt("root", path.join(repo, ".run", "logseq-test")));
const serverPort = Number(opt("server-port", "8791"));
const key = opt("key", "");
const mode = opt("mode", "fake");
const sandbox = (...a) => execFileSync(process.execPath, [path.join(here, "sandbox.mjs"), ...a,
  "--root", root, "--plugin", plugin], { encoding: "utf8", stdio: ["ignore", "pipe", "inherit"] });
if (!key) {
  console.error("--key is required (the same key server.py was started with)");
  process.exit(2);
}

let failures = 0;
function check(name, ok, detail = "") {
  if (!ok) failures += 1;
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? ` -- ${detail}` : ""}`);
}

// ---------------------------------------------------------------- fresh sandbox with the plugin and its settings

if (fs.existsSync(root) && !fs.existsSync(path.join(root, ".logseq-sandbox"))) {
  console.error(`${root} exists but is not a sandbox made by sandbox.mjs prepare; not resetting it.`);
  process.exit(2);
}
sandbox("stop");
for (const d of ["home", "userdata", "graphs", "appdata", "localappdata", "logs", "crashdumps"]) {
  fs.rmSync(path.join(root, d), { recursive: true, force: true, maxRetries: 10, retryDelay: 300 });
}
fs.rmSync(path.join(root, "refine-log.jsonl"), { force: true });
console.log(sandbox("prepare").trim());
const settingsDir = path.join(root, "home", ".logseq", "settings");
fs.mkdirSync(settingsDir, { recursive: true });
fs.writeFileSync(path.join(settingsDir, "agent-stack-refine.json"),
  JSON.stringify({ key, port: serverPort, menuStyles: "concise", disabled: false }, null, 2));
console.log(sandbox("start").trim());
try {
  await steps();
} catch (e) {
  check("the run finished", false, String(e && e.stack || e));
} finally {
  sandbox("stop");
}
console.log(failures ? `${failures} check(s) failed` : "all checks passed");
process.exit(failures ? 1 : 0);

async function steps() {
// ---------------------------------------------------------------- DevTools session

function devtoolsPort() { // Chromium picks a free port and writes it here (sandbox.mjs starts it with port 0)
  try {
    return Number(fs.readFileSync(path.join(root, "userdata", "DevToolsActivePort"), "utf8").split("\n")[0]) || 0;
  } catch {
    return 0;
  }
}

async function connect() {
  for (let i = 0; i < 120; i++) {
    try {
      const port = devtoolsPort();
      if (!port) throw new Error("no DevTools port yet");
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = list.find((t) => t.type === "page" && /index\.html/.test(t.url));
      if (page) {
        const ws = new WebSocket(page.webSocketDebuggerUrl);
        await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
        return ws;
      }
    } catch { /* starting */ }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("no Logseq window");
}
const ws = await connect();
let nextId = 0;
const waiting = new Map();
ws.onmessage = (m) => {
  const msg = JSON.parse(m.data);
  if (waiting.has(msg.id)) {
    waiting.get(msg.id)(msg);
    waiting.delete(msg.id);
  }
};
function cdp(method, params) {
  const id = ++nextId;
  return new Promise((resolve) => {
    waiting.set(id, resolve);
    ws.send(JSON.stringify({ id, method, params }));
  });
}
async function press(name, code, vk) { // a key press as DevTools input, delivered to the focused element of the page
  for (const type of ["keyDown", "keyUp"]) {
    await cdp("Input.dispatchKeyEvent", { type, key: name, code, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk });
  }
}
async function typeKeys(text) { // real key events: Logseq opens its / menu on a "/" key typed after a space
  for (const ch of text) {
    await cdp("Input.dispatchKeyEvent", { type: "keyDown", key: ch, text: ch, unmodifiedText: ch });
    await cdp("Input.dispatchKeyEvent", { type: "keyUp", key: ch });
  }
}
async function js(expression) {
  const reply = await cdp("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true, timeout: 120000 });
  const r = reply.result || {};
  if (reply.error || r.exceptionDetails) {
    throw new Error(JSON.stringify(reply.error || r.exceptionDetails.exception?.description || r.exceptionDetails));
  }
  return r.result.value;
}

// Helpers inside the Logseq window.
await js(`window.__e2e = {
  sleep: (ms) => new Promise((r) => setTimeout(r, ms)),
  async until(fn, ms = 10000) {
    const t0 = Date.now();
    while (Date.now() - t0 < ms) { const v = await fn(); if (v) return v; await this.sleep(100); }
    return null;
  },
  api: () => window.logseq && window.logseq.api,
  async text(uuid) { const b = await this.api().get_block(uuid); return b ? b.fullTitle : null; },
  async raw(uuid) { const b = await this.api().get_block(uuid); return b ? b.title : null; },
  async open(name) {
    location.hash = '#/page/' + encodeURIComponent(name.toLowerCase());
    return !!(await this.until(() => document.querySelector('.ls-block[blockid]')));
  },
  async menu(uuid) {
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await this.sleep(150);
    const blk = await this.until(() => document.querySelector('.ls-block[blockid="' + uuid + '"]'));
    if (!blk) return [];
    const bullet = blk.querySelector('.bullet-container');
    const r = bullet.getBoundingClientRect();
    bullet.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true, view: window, button: 2,
      buttons: 2, clientX: r.x + 8, clientY: r.y + 8 }));
    await this.until(() => document.querySelector('[role=menuitem]'), 3000);
    return [...document.querySelectorAll('[role=menuitem]')].map((e) => e.textContent.trim());
  },
  click(label) {
    const item = [...document.querySelectorAll('[role=menuitem]')].find((e) => e.textContent.trim().startsWith(label));
    if (!item) return false;
    item.click();
    return true;
  },
  notes() { // Logseq 2.0 shows logseq.UI.showMsg as toasts
    return [...document.querySelectorAll('.ui__toaster-viewport .ui__toast')].map((e) => e.innerText.trim()).filter(Boolean);
  },
};`);

const q = (s) => JSON.stringify(s);
const log = () => {
  const file = path.join(root, "refine-log.jsonl");
  return fs.existsSync(file) ? fs.readFileSync(file, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l)) : [];
};
const uuids = (s) => (String(s).match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g) || []).sort();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const ready = await js(`(async () => !!(await __e2e.until(() => window.LSPluginCore &&
  [...LSPluginCore.registeredPlugins.values()].some((p) => p.id === 'agent-stack-refine' && p.loaded), 60000)))()`);
check("plugin loads in the throwaway Logseq", ready);
// A fresh profile creates its first graph while it starts; wait for it before making pages.
const graph = await js(`(async () => {
  const g = await __e2e.until(async () => { try { return await __e2e.api().get_current_graph(); } catch { return null; } }, 60000);
  await __e2e.sleep(1500);
  return g;
})()`);
const graphPath = path.resolve(String((graph && graph.path) || ""));
check("the graph is a throwaway one inside the sandbox", graphPath.toLowerCase().startsWith(path.join(root, "graphs").toLowerCase()),
  `${graph && graph.name} at ${graphPath}`);

// ---------------------------------------------------------------- test page

const BLOCKS = mode === "gateway"
  ? { real: "this are a block that mention [[Project Alpha]] and #idea, writen in a hurry and with to many typo" }
  : {
    first: "this are a first block that mention [[Project Alpha]] and #idea with teh typo",
    props: "second block with a property\nstatus:: draft\nand teh body text",
    good: "All good here.",
    tag: "a block that drop its tag #idea",
    edit: "this block will be edit meanwhile",
    slash: "this are the slash block",
    editing: "this block will be open in the editor",
  };
const page = mode === "gateway" ? "E2E refine real model" : "E2E refine";
const ids = await js(`(async () => {
  const api = __e2e.api();
  await api.create_page(${q(page)}, null, { redirect: false });
  const out = {};
  for (const [k, text] of Object.entries(${q(BLOCKS)})) out[k] = (await api.append_block_in_page(${q(page)}, text)).uuid;
  return out;
})()`);
await js(`__e2e.open(${q(page)})`);
const pagesBefore = await js("(async () => (await __e2e.api().get_all_pages()).length)()");

async function refineWith(uuid, label) {
  const items = await js(`__e2e.menu(${q(uuid)})`);
  const clicked = await js(`__e2e.click(${q(label)})`);
  return { items, clicked };
}
async function waitText(uuid, want, ms = 10000) {
  return js(`__e2e.until(async () => (await __e2e.text(${q(uuid)})) === ${q(want)} || null, ${ms})`);
}

if (mode === "fake") {
  // Refine with the default style from the right-click menu.
  const before = { text: BLOCKS.first, raw: await js(`__e2e.raw(${q(ids.first)})`) };
  const { items, clicked } = await refineWith(ids.first, "Refine with Polish");
  check("right-click menu lists the plugin's items",
    ["Refine with Polish", "Refine with Concise", "Refine with...", "Put back the original (undo refine)"]
      .every((label) => items.includes(label)), items.filter((i) => i.startsWith("Refine") || i.startsWith("Put")).join(" | "));
  check("clicked Refine with Polish", clicked);
  const want = "This is a first block that mentions [[Project Alpha]] and #idea, with the typo fixed.";
  check("the block is replaced with the suggestion", await waitText(ids.first, want), await js(`__e2e.text(${q(ids.first)})`));
  const rawAfter = await js(`__e2e.raw(${q(ids.first)})`);
  check("links and tags still point at the same pages", JSON.stringify(uuids(rawAfter)) === JSON.stringify(uuids(before.raw)),
    rawAfter);
  check("no page was created", (await js("(async () => (await __e2e.api().get_all_pages()).length)()")) === pagesBefore);
  let entry = log().find((e) => e.block === ids.first && e.kind === "refine");
  check("the refine log has the before and after", entry && entry.status === "replaced" && entry.before === before.text
    && entry.after === want && entry.app === "logseq" && entry.page === page, JSON.stringify(entry));

  // Undo from the menu.
  await refineWith(ids.first, "Put back the original");
  check("Put back the original restores the block", await waitText(ids.first, before.text), await js(`__e2e.text(${q(ids.first)})`));
  entry = log().find((e) => e.kind === "revert" && e.block === ids.first);
  check("the revert is logged", entry && entry.status === "replaced" && entry.after === before.text, JSON.stringify(entry));
  check("links survive the undo too", JSON.stringify(uuids(await js(`__e2e.raw(${q(ids.first)})`))) === JSON.stringify(uuids(before.raw)));

  // Property lines are not sent and come back unchanged.
  await refineWith(ids.props, "Refine with Polish");
  check("a property line stays as it was",
    await waitText(ids.props, "Second block, with a property\nstatus:: draft\nAnd the body text."),
    JSON.stringify(await js(`__e2e.text(${q(ids.props)})`)));

  // No changes needed.
  await refineWith(ids.good, "Refine with Polish");
  await sleep(1500);
  check("text that needs no change stays", (await js(`__e2e.text(${q(ids.good)})`)) === BLOCKS.good);
  check("no change is logged as unchanged", log().some((e) => e.block === ids.good && e.status === "unchanged"));

  // A suggestion that drops a tag is rejected; the block stays.
  await refineWith(ids.tag, "Refine with Polish");
  await sleep(1500);
  check("a suggestion that drops a tag is not written", (await js(`__e2e.text(${q(ids.tag)})`)) === BLOCKS.tag);
  entry = log().find((e) => e.block === ids.tag);
  check("the rejected suggestion is kept in the log", entry && entry.status === "rejected" && /markup/.test(entry.note),
    JSON.stringify(entry));

  // You edit the block while the model works: your edit wins, the suggestion is logged as skipped.
  await refineWith(ids.edit, "Refine with Polish");
  await sleep(400);
  await js(`__e2e.api().update_block(${q(ids.edit)}, "I typed this while the model worked")`);
  await sleep(3000);
  check("an edit made meanwhile is kept", (await js(`__e2e.text(${q(ids.edit)})`)) === "I typed this while the model worked");
  entry = log().find((e) => e.block === ids.edit);
  check("the suggestion is logged as skipped", entry && entry.status === "skipped", JSON.stringify(entry));

  // You click into the block while the model works: it is left alone and the suggestion is logged as skipped.
  await refineWith(ids.editing, "Refine with Polish");
  await sleep(500);
  await js(`(async () => { await __e2e.api().edit_block(${q(ids.editing)}); })()`);
  await sleep(3000);
  const stillEditing = await js(`(async () => (await __e2e.api().check_editing()) === ${q(ids.editing)})()`);
  await js("(async () => { await __e2e.api().exit_editing_mode(); })()");
  await sleep(300);
  check("a block you are typing in is not overwritten", stillEditing
    && (await js(`__e2e.text(${q(ids.editing)})`)) === BLOCKS.editing);
  entry = log().find((e) => e.block === ids.editing);
  check("the suggestion for a block being edited is logged as skipped",
    entry && entry.status === "skipped" && /being edited/.test(entry.note), JSON.stringify(entry));

  // "Refine with..." opens the style picker in the plugin's frame; pick Concise.
  await refineWith(ids.first, "Refine with...");
  const picked = await js(`(async () => {
    const frame = await __e2e.until(() => [...document.querySelectorAll('iframe')].find((f) => /logseq-refine/.test(f.src)
      && f.contentDocument && f.contentDocument.querySelector('#picker-list button')), 5000);
    if (!frame) return { ok: false, frames: [...document.querySelectorAll('iframe')].map((f) => f.src) };
    const doc = frame.contentDocument;
    const names = [...doc.querySelectorAll('#picker-list button')].map((b) => b.textContent.trim());
    const focused = doc.activeElement && doc.activeElement.textContent.trim();
    const visible = getComputedStyle(frame).display !== 'none' && getComputedStyle(frame.parentElement).display !== 'none';
    doc.querySelector('#picker-list button[data-style="concise"]').click();
    return { ok: true, names, focused, visible };
  })()`);
  check("the picker lists every style and focuses the first", picked.ok && picked.names.length >= 7
    && /^Polish/.test(picked.focused || "") && picked.visible, JSON.stringify(picked));
  check("picking Concise refines with it", await waitText(ids.first, "First block: mentions [[Project Alpha]] and #idea."),
    await js(`__e2e.text(${q(ids.first)})`));
  check("the log names the picked style", log().some((e) => e.block === ids.first && e.style === "concise" && e.status === "replaced"));
  await refineWith(ids.first, "Put back the original");
  await waitText(ids.first, BLOCKS.first);

  // The slash command, typed at the end of a block being edited.
  await js(`(async () => {
    await __e2e.api().edit_block(${q(ids.slash)});
    await __e2e.sleep(400);
    const a = document.activeElement; // edit_block leaves the cursor at the start
    a.setSelectionRange(a.value.length, a.value.length);
  })()`);
  await typeKeys(" /Refine this");
  const popup = await js(`__e2e.until(() => [...document.querySelectorAll('a.menu-link')]
    .some((e) => /Refine this block/.test(e.textContent || '')), 4000)`);
  await press("Enter", "Enter", 13);
  check("the slash command offers Refine this block", !!popup);
  check("the slash command refines the block", await waitText(ids.slash, "This is the slash block."),
    JSON.stringify(await js(`__e2e.text(${q(ids.slash)})`)));
  check("the slash command left no /command text behind",
    log().some((e) => e.block === ids.slash && e.before === BLOCKS.slash && e.status === "replaced"),
    JSON.stringify(log().find((e) => e.block === ids.slash)));

  // A wrong key changes nothing and says how to fix it.
  await js(`(async () => { const p = LSPluginCore.registeredPlugins.get('agent-stack-refine'); p.settings.set('key', 'wrong'); })()`);
  const entries = log().length;
  await refineWith(ids.first, "Refine with Polish");
  await sleep(1500);
  const notes = await js("__e2e.notes()");
  check("a wrong key changes nothing", (await js(`__e2e.text(${q(ids.first)})`)) === BLOCKS.first && log().length === entries);
  check("a wrong key explains the fix", notes.some((n) => /refine key/i.test(n)), notes.slice(-2).join(" / "));
  await js(`(async () => { LSPluginCore.registeredPlugins.get('agent-stack-refine').settings.set('key', ${q(key)}); })()`);
} else {
  // The real local model through a private gateway.
  const rawBefore = await js(`__e2e.raw(${q(ids.real)})`);
  const t0 = Date.now();
  await refineWith(ids.real, "Refine with Polish");
  const entry = await (async () => {
    for (let i = 0; i < 240; i++) {
      const e = log().find((x) => x.block === ids.real && x.kind === "refine");
      if (e) return e;
      await sleep(500);
    }
    return null;
  })();
  const seconds = ((Date.now() - t0) / 1000).toFixed(1);
  check("the real model's refine is logged", !!entry, entry ? `${entry.status} in ${seconds} s via ${entry.served}` : "no entry");
  await sleep(800);
  const now = await js(`__e2e.text(${q(ids.real)})`);
  console.log(`  before: ${BLOCKS.real}\n  after:  ${now}\n  note:   ${entry && entry.note}`);
  if (entry && entry.status === "replaced") {
    check("the block holds the suggestion", now === entry.after);
    check("links and tags still point at the same pages",
      JSON.stringify(uuids(await js(`__e2e.raw(${q(ids.real)})`))) === JSON.stringify(uuids(rawBefore)));
    await refineWith(ids.real, "Put back the original");
    check("Put back the original restores it", await waitText(ids.real, BLOCKS.real));
  } else {
    check("a refused suggestion leaves the block as it was", now === BLOCKS.real);
  }
}

ws.close();
}
