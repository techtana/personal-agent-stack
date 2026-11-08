/* global logseq */
// Logseq refine plugin: "Refine with <style>" in a block's right-click menu. The block's text goes to the agent stack's
// voice typing app on this PC (POST 127.0.0.1:<port>/plugin/...), which rewrites it with the stack's local model in
// the chosen style, checks the reply and keeps a before/after entry in its refine log. Nothing leaves the machine.
//
// Order of a refine: read the block -> /plugin/refine (model, checks) -> read the block again: still the same? ->
// /plugin/commit (the log entry is written) -> only then updateBlock. When the block changed meanwhile or voice
// typing cannot log, the block stays as it was.
(function () {
  "use strict";

  const core = window.RefineCore;
  const busy = new Set(); // blocks being refined or reverted right now
  let styleInfo = null; // last /plugin/styles answer
  let pickerBlock = null; // the block "Refine with..." is choosing a style for

  const SETTINGS = [
    {
      key: "key", type: "string", default: "", title: "Refine key",
      description: "REFINE_BEARER from the agent stack's .env. In the Agent Stack tray: Overview > Logseq refine " +
        "plugin > Copy key, or run `uv run scripts/stack.py logseq-plugin`.",
    },
    {
      key: "port", type: "number", default: core.DEFAULT_PORT, title: "Voice typing port",
      description: "ports.dictation in the agent stack's machine profile; 8790 unless you changed it.",
    },
    {
      key: "menuStyles", type: "string", default: "", title: "More styles in the right-click menu",
      description: "Style ids separated by commas, for example: concise, grammar, my-voice. The default style always " +
        "has its own item and every style is in Refine with.... Reload the plugin after a change.",
    },
  ];

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  function msg(text, status, timeout) {
    return logseq.UI.showMsg(text, status || "success", { timeout: timeout || 5000 });
  }

  async function call(route, body, timeoutMs) {
    const settings = logseq.settings || {};
    const key = String(settings.key || "").trim();
    if (!key) throw new core.SetupError(`Paste the refine key into this plugin's settings first. ${core.SETUP_HINT}`);
    return logseq.Request._request(core.requestOptions(settings.port, key, route, body, timeoutMs));
  }

  async function loadStyles() {
    const answer = await call("styles", {});
    if (!answer || !answer.ok || !Array.isArray(answer.styles)) throw new core.FriendlyError(core.refusalText(answer));
    styleInfo = answer;
    return answer;
  }

  // The block, its text as Logseq shows it, its page and graph. A block being edited is saved first, so the text
  // sent is what you see.
  async function context(uuid) {
    if ((await logseq.Editor.checkEditing()) === uuid) {
      await logseq.Editor.exitEditingMode(false);
      await sleep(200);
    }
    const block = await logseq.Editor.getBlock(uuid);
    if (!block) return null;
    let page = null;
    let graph = null;
    try {
      if (block.page && block.page.id) page = await logseq.Editor.getPage(block.page.id);
    } catch (e) { /* the page title is only for the log */ }
    try {
      graph = await logseq.App.getCurrentGraph();
    } catch (e) { /* likewise */ }
    return { text: core.blockText(block), page: core.pageTitle(page), graph: graph ? graph.name || "" : "" };
  }

  async function textNow(uuid) {
    return core.blockText(await logseq.Editor.getBlock(uuid));
  }

  // Log first, then write: returns true when the block may be replaced now. A block you are typing in is left alone:
  // its saved text may not have your last keystrokes yet, and the editor would save over the new text.
  async function commit(token, uuid, before) {
    const editing = (await logseq.Editor.checkEditing()) === uuid;
    const same = !editing && core.sameText(await textNow(uuid), before);
    const note = same ? "" : editing ? "the block was being edited" : "the block changed while the model worked";
    const answer = await call("commit", { token, write: same, note });
    if (!answer || !answer.ok) {
      msg(`Voice typing could not log the change, so the block was left as it was (${(answer && answer.error) || "no answer"}).`,
        "error", 9000);
      return false;
    }
    if (!same) {
      msg(`${editing ? "You were typing in the block" : "The block changed while the model worked"}, so it was left ` +
        "as it is. The suggestion is in Refine history (the pencil button's menu).", "warning", 9000);
    }
    return same;
  }

  async function refineBlock(uuid, styleId, styleLabel) {
    if (!uuid) return;
    if (busy.has(uuid)) {
      msg("Still working on this block.", "warning");
      return;
    }
    busy.add(uuid);
    let working = null;
    try {
      const ctx = await context(uuid);
      if (!ctx) {
        msg("That block no longer exists.", "warning");
        return;
      }
      if (!ctx.text.trim()) {
        msg("This block has no text to refine.", "warning");
        return;
      }
      working = await msg(`Refining with ${styleLabel || "the default style"}...`, "success", 130000);
      const answer = await call("refine", {
        text: ctx.text, style: styleId || "", app: "logseq", block: uuid, page: ctx.page, graph: ctx.graph,
      }, core.refineTimeout(styleInfo));
      logseq.UI.closeMsg(working);
      working = null;
      if (!answer || !answer.ok) {
        msg(core.refusalText(answer), answer && answer.status === "rejected" ? "warning" : "error", 9000);
        return;
      }
      if (answer.status === "unchanged") {
        msg(`${answer.style_name} left the block as it is.`, "success");
        return;
      }
      if (!(await commit(answer.token, uuid, ctx.text))) return;
      await logseq.Editor.updateBlock(uuid, answer.text);
      msg(`Refined with ${answer.style_name}. To undo it: right-click the bullet > Put back the original.`, "success", 6000);
    } catch (e) {
      msg(core.errorText(e), "error", 9000);
    } finally {
      if (working) logseq.UI.closeMsg(working);
      busy.delete(uuid);
    }
  }

  async function revertBlock(uuid) {
    if (!uuid || busy.has(uuid)) return;
    busy.add(uuid);
    try {
      const ctx = await context(uuid);
      if (!ctx) return;
      const answer = await call("revert", { text: ctx.text, block: uuid, app: "logseq", page: ctx.page, graph: ctx.graph });
      if (!answer || !answer.ok) {
        msg(core.revertRefusalText(answer), "warning", 9000);
        return;
      }
      if (!(await commit(answer.token, uuid, ctx.text))) return;
      await logseq.Editor.updateBlock(uuid, answer.text);
      const extra = answer.match < 1 ? " Edits made after that refine were undone too." : "";
      msg(`Original put back (${answer.style_name || "refine"} from ${core.when(answer.when)}).${extra}`, "success", 7000);
    } catch (e) {
      msg(core.errorText(e), "error", 9000);
    } finally {
      busy.delete(uuid);
    }
  }

  // ---------------------------------------------------------------- "Refine with..." picker (this plugin's own frame)

  const $ = (id) => document.getElementById(id);

  function buttons() {
    return Array.from($("picker-list").querySelectorAll("button"));
  }

  async function openPicker(uuid) {
    let info;
    try {
      info = await loadStyles();
    } catch (e) {
      msg(core.errorText(e), "error", 9000);
      return;
    }
    pickerBlock = uuid;
    const list = $("picker-list");
    list.textContent = "";
    for (const s of info.styles) {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.style = s.id;
      button.textContent = s.name;
      if (s.id === info.default) {
        const tag = document.createElement("span");
        tag.className = "default";
        tag.textContent = "default";
        button.append(" ", tag);
      }
      item.append(button);
      list.append(item);
    }
    $("picker-note").textContent = `Rewritten by ${info.model} on this PC. The original stays in Refine history.`;
    $("backdrop").hidden = false;
    logseq.showMainUI({ autoFocus: true });
    await sleep(30);
    const first = buttons()[0];
    if (first) first.focus();
  }

  function closePicker() {
    $("backdrop").hidden = true;
    pickerBlock = null;
    logseq.hideMainUI({ restoreEditingCursor: false });
  }

  function wirePicker() {
    $("picker-list").addEventListener("click", (event) => {
      const button = event.target.closest("button[data-style]");
      if (!button) return;
      const uuid = pickerBlock;
      const id = button.dataset.style;
      closePicker();
      refineBlock(uuid, id, core.styleName(styleInfo && styleInfo.styles, id));
    });
    $("picker-cancel").addEventListener("click", closePicker);
    $("backdrop").addEventListener("mousedown", (event) => {
      if (event.target === $("backdrop")) closePicker();
    });
    document.addEventListener("keydown", (event) => {
      if ($("backdrop").hidden) return;
      const all = [...buttons(), $("picker-cancel")];
      const at = all.indexOf(document.activeElement);
      if (event.key === "Escape") {
        event.preventDefault();
        closePicker();
      } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const step = event.key === "ArrowDown" ? 1 : -1;
        all[(at + step + all.length) % all.length].focus();
      } else if (event.key === "Tab") { // keep the focus inside the dialog
        event.preventDefault();
        all[(at + (event.shiftKey ? -1 : 1) + all.length) % all.length].focus();
      }
    });
  }

  function setTheme(mode) {
    document.documentElement.dataset.theme = mode === "dark" ? "dark" : "light";
  }

  // ---------------------------------------------------------------- start

  async function main() {
    logseq.useSettingsSchema(SETTINGS);
    logseq.setMainUIInlineStyle({ position: "fixed", inset: "0", zIndex: 999 });
    wirePicker();
    try {
      setTheme((await logseq.App.getUserConfigs()).preferredThemeMode);
    } catch (e) { /* light */ }
    logseq.App.onThemeModeChanged(({ mode }) => setTheme(mode));

    let info = null;
    try {
      info = await loadStyles();
    } catch (e) {
      console.info("[refine] styles not loaded yet:", e && e.message);
    }
    const defId = info ? info.default : "";
    const defName = info ? core.styleName(info.styles, defId) : "";
    logseq.Editor.registerBlockContextMenuItem(defName ? `Refine with ${defName}` : "Refine with the default style",
      ({ uuid }) => refineBlock(uuid, defId, defName));
    for (const s of core.menuStyles(logseq.settings && logseq.settings.menuStyles, info && info.styles, defId)) {
      logseq.Editor.registerBlockContextMenuItem(`Refine with ${s.name}`, ({ uuid }) => refineBlock(uuid, s.id, s.name));
    }
    logseq.Editor.registerBlockContextMenuItem("Refine with...", ({ uuid }) => openPicker(uuid));
    logseq.Editor.registerBlockContextMenuItem("Put back the original (undo refine)", ({ uuid }) => revertBlock(uuid));
    logseq.Editor.registerSlashCommand("Refine this block", ({ uuid }) => refineBlock(uuid, defId, defName));
  }

  logseq.ready(main).catch((e) => console.error("[refine] could not start", e));
})();
