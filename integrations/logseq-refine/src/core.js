// Logic of the Logseq refine plugin that does not touch Logseq: what text to send, which styles go in the menu, the
// request to voice typing, and the messages you see. Loaded by index.html (window.RefineCore) and by the Node tests.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.RefineCore = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const DEFAULT_PORT = 8790;
  const REQUEST_TIMEOUT_MS = 150000; // until /plugin/styles says how long voice typing gives the model (timeout_s)
  const MAX_MENU_STYLES = 6;
  const SETUP_HINT = "In the Agent Stack tray: Overview > Logseq refine plugin > Copy key, then paste it into this " +
    "plugin's settings (Settings > Plugins > Refine with the local AI > gear).";

  class FriendlyError extends Error {} // its message is already a sentence for you
  class SetupError extends FriendlyError {}

  // The block's text as Logseq shows it. In database graphs `title` stores links and tags by id ([[<uuid>]],
  // #[[<uuid>]]) and `fullTitle` by name; the name form is what you edit, what the model can read, and what Logseq
  // turns back into the same links when it is written. Writing the id form of a tag made Logseq 2.0.2 create a new tag
  // named after the uuid.
  function blockText(block) {
    if (!block) return "";
    for (const field of ["fullTitle", "content", "title"]) {
      if (typeof block[field] === "string") return block[field];
    }
    return "";
  }

  // Same text, whitespace aside: what decides whether the block changed while the model worked.
  function sameText(a, b) {
    const norm = (s) => String(s || "").split(/\s+/).filter(Boolean).join(" ");
    return norm(a) === norm(b);
  }

  function graphName(graph) {
    const name = graph && typeof graph.name === "string" ? graph.name : "";
    return name.startsWith("logseq_db_") ? name.slice("logseq_db_".length) : name;
  }

  function pageTitle(page) {
    if (!page) return "";
    return page.title || page.originalName || page.name || "";
  }

  function validPort(value) {
    const n = Number(value);
    return Number.isInteger(n) && n > 0 && n < 65536 ? n : DEFAULT_PORT;
  }

  // Styles named in the "More styles in the right-click menu" setting, in that order, known ones only, without the
  // default (it has its own item), at most MAX_MENU_STYLES.
  function menuStyles(setting, styles, defaultId) {
    const known = new Map((styles || []).map((s) => [s.id, s]));
    const out = [];
    for (const raw of String(setting || "").split(/[,;\n]/)) {
      const id = raw.trim();
      if (!id || id === defaultId || !known.has(id) || out.some((s) => s.id === id)) continue;
      out.push(known.get(id));
      if (out.length >= MAX_MENU_STYLES) break;
    }
    return out;
  }

  function styleName(styles, id) {
    const hit = (styles || []).find((s) => s.id === id);
    return hit ? hit.name : "";
  }

  // logseq.Request._request options: sent by Logseq's main process (node-fetch), so the request has no Origin header
  // and voice typing's rule against web pages does not apply to it. Its answer is the parsed JSON body, whatever the
  // HTTP status, so voice typing puts ok/error in every body.
  function requestOptions(port, key, route, body, timeoutMs) {
    return {
      url: `http://127.0.0.1:${validPort(port)}/plugin/${route}`,
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
      data: body || {},
      returnType: "json",
      timeout: timeoutMs || REQUEST_TIMEOUT_MS,
    };
  }

  // How long to wait for a refine: voice typing's own model timeout (refine.timeout_s, 10 to 600 s) plus 30 s.
  function refineTimeout(info) {
    const s = Number(info && info.timeout_s);
    return Number.isFinite(s) && s > 0 ? Math.min(Math.max(s, 10), 600) * 1000 + 30000 : REQUEST_TIMEOUT_MS;
  }

  function errorText(err) {
    if (err instanceof FriendlyError) return err.message;
    const text = String((err && (err.message || err.reason)) || err || "");
    if (/ECONNREFUSED|ECONNRESET|socket hang up|failed, reason/i.test(text)) {
      return "Voice typing is not running, and refining goes through it. Start Voice typing in the Agent Stack tray " +
        "(Overview), then try again.";
    }
    if (/abort|timeout|timed out/i.test(text)) return "The local model took too long to answer. Nothing was changed.";
    if (/JSON|Unexpected token/i.test(text)) {
      return "Something else answers on the voice typing port. Check the port in this plugin's settings.";
    }
    return `Could not refine the block: ${text || "unknown error"}. Nothing was changed.`;
  }

  // What to tell you about an answer that is not ok (rejected, failed, refused). Every one leaves the block as it was.
  function refusalText(answer) {
    const error = String((answer && answer.error) || "");
    if (/REFINE_BEARER to check/.test(error)) {
      return "Voice typing has no refine key yet. Run Set up on the Logseq refine plugin row in the Agent Stack tray.";
    }
    if (/refine key|REFINE_BEARER/.test(error)) return `The refine key is missing or wrong. ${SETUP_HINT}`;
    if (/longer than/.test(error)) return `This block is too long to refine at once (${error}). Split it first.`;
    if (answer && answer.status === "rejected") {
      return `Kept your text: ${error}. The suggestion is in Refine history (the pencil button's menu).`;
    }
    if (answer && answer.status === "failed") return `Could not refine the block: ${error}. Nothing was changed.`;
    return `Voice typing refused the request${error ? `: ${error}` : ""}. Nothing was changed.`;
  }

  function revertRefusalText(answer) {
    if (answer && answer.status === "none") {
      return "Nothing to put back: this block has no refine in the history (only refines made from this menu count).";
    }
    if (answer && answer.status === "changed") {
      return "This block has changed too much since it was refined, so it was left as it is. Refine history (the " +
        "pencil button's menu) has the original to copy.";
    }
    return refusalText(answer);
  }

  function when(iso) {
    return String(iso || "").slice(0, 16).replace("T", " ");
  }

  return {
    DEFAULT_PORT, REQUEST_TIMEOUT_MS, MAX_MENU_STYLES, SETUP_HINT, FriendlyError, SetupError,
    blockText, sameText, graphName, pageTitle, validPort, menuStyles, styleName, requestOptions, refineTimeout,
    errorText, refusalText, revertRefusalText, when,
  };
});
