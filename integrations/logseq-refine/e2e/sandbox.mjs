#!/usr/bin/env node
// A throwaway copy of Logseq for testing the plugin, isolated from your own Logseq (Windows only).
//
//   node e2e/sandbox.mjs prepare [--root DIR] [--plugin DIR]   copy the installed Logseq and seed an empty profile
//   node e2e/sandbox.mjs start   [--root DIR]                  start it, with Chrome DevTools on a free local port
//   node e2e/sandbox.mjs eval    [--root DIR] "<js>"            run JavaScript in its window, print the result
//   node e2e/sandbox.mjs stop    [--root DIR]                  stop it
//   node e2e/sandbox.mjs clean   [--root DIR]                  stop it and delete the whole folder
// stop, clean and run.mjs delete only a folder that prepare marked with SANDBOX_MARK.
//
// Why a copy: Logseq keeps its plugin list, plugin settings and graph list in ~/.logseq, found through Electron's
// app.getPath("home"), and Windows ignores USERPROFILE for that folder. In the copy, app.asar is renamed to
// logseq.asar: Electron looks for app.asar, then an "app" folder (the OnlyLoadAppFromAsar fuse is off in Logseq
// 2.0.2), so it starts resources/app/boot.js instead. boot.js points home, appData and userData at folders under
// --root, then loads logseq.asar/electron.js. `start` refuses to run a copy that still has app.asar, and stops the
// copy again if boot.js does not report in, because without it Logseq would read and write your own ~/.logseq.
// boot.js also keeps the copy from registering logseq:// links or changing the taskbar jump list. app-update.yml is
// deleted from the copy, so it cannot update itself. LOCALAPPDATA points under --root, where Logseq installs its
// logseq.cmd launcher; with the renamed archive that install fails, and boot.js logs Logseq's error box about it
// instead of leaving a modal box on the screen. LOGSEQ_GRAPHS_DIR keeps database
// graphs under --root. A proxy that goes nowhere blocks web requests from the window (Chromium's network stack only;
// requests from Logseq's main process, such as a plugin's logseq.Request, go out directly); loopback stays reachable.
// DevTools listens on a free port that Chromium picks and writes to userdata/DevToolsActivePort. The window opens
// off-screen without a taskbar button or focus (LOGSEQ_SANDBOX_VISIBLE=1 shows it). The installed Logseq and its
// files are only read.
import { spawn, execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const args = process.argv.slice(2);
const command = args.shift();
const opt = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  if (i < 0) return fallback;
  const [value] = args.splice(i, 2).slice(1);
  return value;
};
const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, "..", "..", "..");
const root = path.resolve(opt("root", path.join(repo, ".run", "logseq-test")));
const SANDBOX_MARK = ".logseq-sandbox"; // prepare writes it; nothing else is ever deleted
const plugin = path.resolve(opt("plugin", path.resolve(here, "..")));
const installed = opt("logseq", path.join(process.env.LOCALAPPDATA || "", "Programs", "Logseq"));
const app = path.join(root, "app");

const BOOT = `'use strict';
// Test-only start-up of an isolated Logseq copy (integrations/logseq-refine/e2e/sandbox.mjs).
const path = require('path');
const fs = require('fs');
const { app, dialog } = require('electron');
const root = process.env.LOGSEQ_SANDBOX_ROOT;
// An error box is modal and would wait on the screen for a click (the copy's launcher install fails, for one).
dialog.showErrorBox = (title, content) => console.error('[sandbox] error box not shown: ' + title + ': ' + content);
if (!root || !fs.existsSync(root)) {
  console.error('[sandbox] LOGSEQ_SANDBOX_ROOT is not set; refusing to start with the real profile');
  app.exit(2);
} else {
  const asar = path.join(process.resourcesPath, 'logseq.asar');
  for (const [name, dir] of [['home', 'home'], ['appData', 'appdata'], ['userData', 'userdata'], ['crashDumps', 'crashdumps']]) {
    const p = path.join(root, dir);
    fs.mkdirSync(p, { recursive: true });
    app.setPath(name, p);
  }
  app.setAppLogsPath(path.join(root, 'logs'));
  app.setAppUserModelId('agent-stack.logseq-sandbox');
  app.setAppUserModelId = () => {};
  app.setAsDefaultProtocolClient = () => false;
  app.removeAsDefaultProtocolClient = () => false;
  app.setJumpList = () => 'ok';
  app.setUserTasks = () => true;
  app.setLoginItemSettings = () => {};
  app.getAppPath = () => asar;
  if (process.env.LOGSEQ_SANDBOX_VISIBLE !== '1') {
    // Keep the test window out of your way: off-screen, no taskbar button, never activated, still rendering.
    app.on('browser-window-created', (_event, win) => {
      const park = () => { try { if (win.getPosition()[0] > -20000) win.setPosition(-30000, -30000); } catch (e) { /* closed */ } };
      try {
        win.setSkipTaskbar(true);
        win.webContents.setBackgroundThrottling(false);
        win.show = () => { park(); win.showInactive(); };
        win.focus = () => {};
        win.moveTop = () => {};
        win.maximize = () => {};
        win.setFullScreen = () => {};
        win.on('move', park);
        win.on('show', park);
        park();
      } catch (e) {
        console.error('[sandbox] could not park a window: ' + e.message);
      }
    });
  }
  console.log('[sandbox] home=' + app.getPath('home') + ' userData=' + app.getPath('userData'));
  require(path.join(asar, 'electron.js'));
}
`;
const BOOT_MARK = "[sandbox] home=";

function die(msg) {
  console.error(msg);
  process.exit(1);
}

function prepare() {
  if (process.platform !== "win32") die("The sandbox copies the Windows install of Logseq; run it on Windows.");
  if (!fs.existsSync(path.join(installed, "Logseq.exe"))) die(`No Logseq at ${installed} (--logseq DIR).`);
  const asarStat = fs.statSync(path.join(installed, "resources", "app.asar"));
  const stamp = path.join(app, ".copied-from");
  const want = `${installed}|${asarStat.size}|${asarStat.mtimeMs}`;
  if (!fs.existsSync(stamp) || fs.readFileSync(stamp, "utf8") !== want) {
    fs.rmSync(app, { recursive: true, force: true });
    console.log(`copying ${installed} -> ${app}`);
    fs.cpSync(installed, app, { recursive: true });
    fs.writeFileSync(stamp, want);
  }
  const res = path.join(app, "resources");
  fs.rmSync(path.join(res, "app-update.yml"), { force: true });
  for (const [from, to] of [["app.asar", "logseq.asar"], ["app.asar.unpacked", "logseq.asar.unpacked"]]) {
    if (fs.existsSync(path.join(res, from))) fs.renameSync(path.join(res, from), path.join(res, to));
  }
  const boot = path.join(res, "app");
  fs.mkdirSync(boot, { recursive: true });
  const real = JSON.parse(execFileSync(process.execPath, [path.join(here, "asar-read.cjs"),
    path.join(res, "logseq.asar"), "package.json"], { encoding: "utf8" }));
  fs.writeFileSync(path.join(boot, "package.json"), JSON.stringify({
    name: real.name, productName: real.productName, version: real.version, main: "boot.js",
  }, null, 2));
  fs.writeFileSync(path.join(boot, "boot.js"), BOOT);
  for (const d of ["home/.logseq", "appdata", "localappdata", "userdata", "graphs", "logs"]) {
    fs.mkdirSync(path.join(root, d), { recursive: true });
  }
  fs.writeFileSync(path.join(root, SANDBOX_MARK), "a throwaway Logseq made by integrations/logseq-refine/e2e/sandbox.mjs\n");
  const prefs = path.join(root, "home", ".logseq", "preferences.json");
  const current = fs.existsSync(prefs) ? JSON.parse(fs.readFileSync(prefs, "utf8")) : {};
  const externals = new Set([...(current.externals || []), plugin]);
  fs.writeFileSync(prefs, JSON.stringify({ theme: null, themes: { mode: "light", light: null, dark: null },
    ...current, externals: [...externals] }, null, 2));
  console.log(`ready: ${root} (Logseq ${real.version}); plugin ${plugin}`);
}

async function start() {
  const exe = path.join(app, "Logseq.exe");
  const res = path.join(app, "resources");
  if (!fs.existsSync(exe)) die("Run prepare first.");
  if (fs.existsSync(path.join(res, "app.asar")) || !fs.existsSync(path.join(res, "app", "boot.js"))) {
    die("The copy would start Logseq's own code with your real ~/.logseq (app.asar present or boot.js missing); "
      + "run prepare again.");
  }
  const env = {
    ...process.env,
    ELECTRON_RUN_AS_NODE: undefined,
    NODE_OPTIONS: undefined,
    LOGSEQ_SANDBOX_ROOT: root,
    LOGSEQ_GRAPHS_DIR: path.join(root, "graphs"),
    USERPROFILE: path.join(root, "home"),
    HOME: path.join(root, "home"),
    APPDATA: path.join(root, "appdata"),
    LOCALAPPDATA: path.join(root, "localappdata"),
    ELECTRON_ENABLE_LOGGING: "1",
  };
  for (const key of Object.keys(env)) if (env[key] === undefined) delete env[key];
  const logFile = path.join(root, "logs", "stdout.log");
  const portFile = path.join(root, "userdata", "DevToolsActivePort");
  fs.rmSync(logFile, { force: true });
  fs.rmSync(portFile, { force: true });
  const out = fs.openSync(logFile, "a");
  const child = spawn(exe, ["--remote-debugging-port=0", "--proxy-server=http://127.0.0.1:9",
    `--user-data-dir=${path.join(root, "userdata")}`, "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding", "--disable-background-timer-throttling"],
  { env, detached: true, stdio: ["ignore", out, out] });
  fs.writeFileSync(path.join(root, "pid"), String(child.pid));
  child.unref();
  const home = path.join(root, "home");
  for (let i = 0; i < 60; i++) {
    await new Promise((r) => setTimeout(r, 250));
    const line = fs.readFileSync(logFile, "utf8").split(/\r?\n/).find((l) => l.includes(BOOT_MARK));
    if (line) {
      if (!line.includes(`${BOOT_MARK}${home} `)) {
        await stop();
        die(`boot.js reported another home folder; stopped. ${line}`);
      }
      for (let j = 0; j < 40 && !fs.existsSync(portFile); j++) await new Promise((r) => setTimeout(r, 250));
      console.log(`started pid ${child.pid}; DevTools on 127.0.0.1:${devtoolsPort()}`);
      return;
    }
  }
  await stop();
  die("boot.js did not report in within 15 s; the copy was stopped. See logs/stdout.log.");
}

function devtoolsPort(dir = root) {
  try {
    return Number(fs.readFileSync(path.join(dir, "userdata", "DevToolsActivePort"), "utf8").split(/\r?\n/)[0]) || 0;
  } catch {
    return 0;
  }
}

async function page() {
  for (let i = 0; i < 120; i++) {
    const port = devtoolsPort();
    try {
      if (!port) throw new Error("no port yet");
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const main = list.find((t) => t.type === "page" && /index\.html/.test(t.url));
      if (main) return main;
    } catch { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 500));
  }
  die(`No Logseq window on DevTools port ${devtoolsPort() || "(none yet)"}.`);
}

async function evaluate(expression) {
  const target = await page();
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  const reply = await new Promise((resolve) => {
    const timer = setTimeout(() => resolve({ error: "no answer within 150 s (a modal dialog in the copy?)" }), 150000);
    ws.onmessage = (m) => {
      const msg = JSON.parse(m.data);
      if (msg.id === 1) {
        clearTimeout(timer);
        resolve(msg);
      }
    };
    ws.send(JSON.stringify({ id: 1, method: "Runtime.evaluate",
      params: { expression, awaitPromise: true, returnByValue: true, timeout: 120000 } }));
  });
  ws.close();
  if (reply.error) die(JSON.stringify(reply.error));
  const { result, exceptionDetails } = reply.result;
  if (exceptionDetails) die(exceptionDetails.exception?.description || exceptionDetails.text);
  return result.value;
}

// Processes started from the copy's own Logseq.exe; the installed Logseq's never match.
function copyProcesses() {
  const exe = path.join(app, "Logseq.exe").toLowerCase();
  const rows = execFileSync("powershell", ["-NoProfile", "-Command",
    "Get-CimInstance Win32_Process -Filter \"Name='Logseq.exe'\" | ForEach-Object { \"$($_.ProcessId)|$($_.ExecutablePath)\" }"],
  { encoding: "utf8" }).split(/\r?\n/).filter(Boolean);
  return rows.map((row) => row.split("|")).filter(([, file]) => (file || "").toLowerCase() === exe).map(([id]) => Number(id));
}

async function stop() {
  const pidFile = path.join(root, "pid");
  try {
    for (let i = 0; i < 40; i++) { // up to 10 s for every process of the copy to exit and free its files
      const pids = copyProcesses();
      if (!pids.length) break;
      if (i % 10 === 0) {
        for (const id of pids) {
          try { process.kill(id); } catch { /* already gone */ }
        }
      }
      await new Promise((r) => setTimeout(r, 250));
    }
  } catch (e) {
    console.error(`could not list processes (${e.message})`);
  }
  fs.rmSync(pidFile, { force: true });
  console.log("stopped");
}

if (command === "prepare") prepare();
else if (command === "start") await start();
else if (command === "eval") console.log(JSON.stringify(await evaluate(args.join(" ")), null, 2));
else if (command === "stop") await stop();
else if (command === "clean") {
  if (!fs.existsSync(path.join(root, SANDBOX_MARK))) die(`${root} has no ${SANDBOX_MARK}; not deleting it.`);
  await stop();
  fs.rmSync(root, { recursive: true, force: true, maxRetries: 10, retryDelay: 300 });
  console.log(`deleted ${root}`);
} else if (command) die("usage: sandbox.mjs prepare|start|eval|stop|clean [--root DIR] [--plugin DIR]");
