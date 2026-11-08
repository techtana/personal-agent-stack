// node --test test/   (no dependencies; core.js is plain JavaScript shared with the plugin page)
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { test } from "node:test";

const core = createRequire(import.meta.url)("../src/core.js");

const STYLES = [
  { id: "polish", name: "Polish" }, { id: "grammar", name: "Fix spelling and grammar only" },
  { id: "concise", name: "Concise" }, { id: "my-voice", name: "My voice" },
];

test("blockText prefers the names Logseq shows over the stored id form", () => {
  const block = {
    title: "mention [[6af021c1-e102-437c-9577-34e5ac70fb93]] and #[[6af021c1-a5c2-4d1f-9d17-50e8f60687d5]]",
    content: "mention [[6af021c1-e102-437c-9577-34e5ac70fb93]] and #[[6af021c1-a5c2-4d1f-9d17-50e8f60687d5]]",
    fullTitle: "mention [[Project Alpha]] and #idea",
  };
  assert.equal(core.blockText(block), "mention [[Project Alpha]] and #idea");
  assert.equal(core.blockText({ content: "file graph text" }), "file graph text");
  assert.equal(core.blockText({ title: "only a title" }), "only a title");
  assert.equal(core.blockText({ fullTitle: "" , title: "x" }), "", "an empty fullTitle is the block's text");
  assert.equal(core.blockText(null), "");
});

test("sameText ignores whitespace only", () => {
  assert.ok(core.sameText("a  b\nc ", " a b c"));
  assert.ok(!core.sameText("a b c", "a b d"));
  assert.ok(core.sameText("", null));
});

test("graphName drops the database prefix; pageTitle falls back", () => {
  assert.equal(core.graphName({ name: "logseq_db_Notes" }), "Notes");
  assert.equal(core.graphName({ name: "Old" }), "Old");
  assert.equal(core.graphName(null), "");
  assert.equal(core.pageTitle({ name: "refine test", title: "Refine test" }), "Refine test");
  assert.equal(core.pageTitle({ name: "refine test" }), "refine test");
  assert.equal(core.pageTitle(null), "");
});

test("validPort accepts TCP ports only", () => {
  assert.equal(core.validPort(8791), 8791);
  assert.equal(core.validPort("8792"), 8792);
  for (const bad of [0, 70000, "x", null, undefined, 1.5, -3]) assert.equal(core.validPort(bad), core.DEFAULT_PORT);
});

test("menuStyles keeps known ids in order, without the default or repeats", () => {
  const out = core.menuStyles(" concise, polish, nope; my-voice,concise", STYLES, "polish");
  assert.deepEqual(out.map((s) => s.id), ["concise", "my-voice"]);
  assert.deepEqual(core.menuStyles("", STYLES, "polish"), []);
  assert.deepEqual(core.menuStyles("concise", null, "polish"), []);
  const many = Array.from({ length: 10 }, (_, i) => ({ id: `s${i}`, name: `S${i}` }));
  assert.equal(core.menuStyles(many.map((s) => s.id).join(","), many, "").length, core.MAX_MENU_STYLES);
});

test("styleName finds a style's display name", () => {
  assert.equal(core.styleName(STYLES, "concise"), "Concise");
  assert.equal(core.styleName(STYLES, "missing"), "");
  assert.equal(core.styleName(null, "x"), "");
});

test("requestOptions aims at voice typing on loopback with the bearer key", () => {
  const o = core.requestOptions(8791, "k3y", "refine", { text: "hi" });
  assert.equal(o.url, "http://127.0.0.1:8791/plugin/refine");
  assert.equal(o.method, "POST");
  assert.equal(o.headers.Authorization, "Bearer k3y");
  assert.equal(o.headers["Content-Type"], "application/json");
  assert.deepEqual(o.data, { text: "hi" });
  assert.equal(o.returnType, "json");
  assert.ok(o.timeout > 120000, "longer than the model's own timeout");
  assert.equal(core.requestOptions("nonsense", "k", "styles").url, "http://127.0.0.1:8790/plugin/styles");
});

test("refineTimeout follows voice typing's model timeout", () => {
  assert.equal(core.refineTimeout({ timeout_s: 120 }), 150000);
  assert.equal(core.refineTimeout({ timeout_s: 600 }), 630000);
  assert.equal(core.refineTimeout({ timeout_s: 9000 }), 630000, "capped like refine.timeout_s");
  assert.equal(core.refineTimeout(null), core.REQUEST_TIMEOUT_MS);
  assert.equal(core.refineTimeout({ timeout_s: "x" }), core.REQUEST_TIMEOUT_MS);
  assert.equal(core.requestOptions(8790, "k", "refine", {}, 630000).timeout, 630000);
});

test("errorText explains the usual failures", () => {
  assert.match(core.errorText(new Error("request to http://127.0.0.1:8790/plugin/refine failed, reason: connect ECONNREFUSED 127.0.0.1:8790")),
    /Voice typing is not running/);
  assert.match(core.errorText(new Error("The user aborted a request.")), /took too long/);
  assert.match(core.errorText(new Error("Unexpected token < in JSON at position 0")), /Something else answers/);
  assert.equal(core.errorText(new core.SetupError("Paste the key.")), "Paste the key.");
  assert.equal(core.errorText(new core.FriendlyError("Already a sentence.")), "Already a sentence.");
  assert.match(core.errorText("weird"), /Could not refine the block: weird/);
});

test("refusalText turns voice typing's answers into advice", () => {
  assert.match(core.refusalText({ ok: false, error: "voice typing has no REFINE_BEARER to check plugins with; run x" }),
    /Run Set up/);
  assert.match(core.refusalText({ ok: false, error: "the key is not this stack's REFINE_BEARER" }), /Copy key/);
  assert.match(core.refusalText({ ok: false, error: "text is longer than 10,000 characters" }), /too long/);
  assert.match(core.refusalText({ ok: false, status: "rejected", error: "the model changed Logseq markup (x)" }),
    /^Kept your text: the model changed Logseq markup/);
  assert.match(core.refusalText({ ok: false, status: "failed", error: "the gateway is not reachable" }),
    /Could not refine the block: the gateway is not reachable/);
  assert.equal(core.refusalText({ ok: false, error: "still refining another block" }),
    "Voice typing refused the request: still refining another block. Nothing was changed.");
  assert.match(core.refusalText({ ok: false, error: "[:div \"looks like markup\"]" }), /^Voice typing refused/,
    "a message never starts with text from the server");
  assert.match(core.refusalText(null), /^Voice typing refused the request\. /);
});

test("revertRefusalText covers no entry and a changed block", () => {
  assert.match(core.revertRefusalText({ ok: false, status: "none" }), /Nothing to put back/);
  assert.match(core.revertRefusalText({ ok: false, status: "changed" }), /changed too much/);
  assert.match(core.revertRefusalText({ ok: false, error: "the key is not this stack's REFINE_BEARER" }), /key/);
});

test("when trims an ISO time to the minute", () => {
  assert.equal(core.when("2026-11-08T01:02:03-07:00"), "2026-11-08 01:02");
  assert.equal(core.when(undefined), "");
});
