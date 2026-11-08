// Build the plugin into dist/: the files in src/ plus @logseq/libs' lsplugin.user.js from node_modules (npm ci first).
// No bundler: the plugin is three small scripts loaded in order by index.html, and nothing is fetched at run time.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(here, "src");
const dist = path.join(here, "dist");
const lib = path.join(here, "node_modules", "@logseq", "libs");
const pinned = JSON.parse(fs.readFileSync(path.join(here, "package.json"), "utf8")).devDependencies["@logseq/libs"];

if (!fs.existsSync(path.join(lib, "dist", "lsplugin.user.js"))) {
  console.error("node_modules/@logseq/libs is missing: run `npm ci` in integrations/logseq-refine first.");
  process.exit(1);
}
const installed = JSON.parse(fs.readFileSync(path.join(lib, "package.json"), "utf8")).version;
if (installed !== pinned) {
  console.error(`@logseq/libs ${installed} is installed but package.json pins ${pinned}: run \`npm ci\`.`);
  process.exit(1);
}
for (const file of ["core.js", "main.js"]) {
  execFileSync(process.execPath, ["--check", path.join(src, file)], { stdio: "inherit" }); // syntax check
}
fs.rmSync(dist, { recursive: true, force: true });
fs.mkdirSync(dist);
for (const file of ["index.html", "style.css", "core.js", "main.js"]) {
  fs.copyFileSync(path.join(src, file), path.join(dist, file));
}
fs.copyFileSync(path.join(lib, "dist", "lsplugin.user.js"), path.join(dist, "lsplugin.user.js"));
console.log(`built ${path.relative(process.cwd(), dist) || "dist"} with @logseq/libs ${installed}`);
