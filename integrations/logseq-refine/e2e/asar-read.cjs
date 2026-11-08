// Print one file from an Electron asar archive (read only): node asar-read.cjs <app.asar> <path inside>
// Format: 16-byte header (pickle sizes; the JSON index length at byte 12), the JSON index, then the file bodies.
"use strict";
const fs = require("fs");

const [, , archive, wanted] = process.argv;
const fd = fs.openSync(archive, "r");
const head = Buffer.alloc(16);
fs.readSync(fd, head, 0, 16, 0);
const indexSize = head.readUInt32LE(12);
const index = Buffer.alloc(indexSize);
fs.readSync(fd, index, 0, indexSize, 16);
const base = 8 + head.readUInt32LE(4);
let node = JSON.parse(index.toString("utf8"));
for (const part of wanted.split("/")) {
  node = node.files && node.files[part];
  if (!node) {
    console.error(`${wanted} is not in ${archive}`);
    process.exit(1);
  }
}
if (node.unpacked || node.files) {
  console.error(`${wanted} is a folder or lives in app.asar.unpacked`);
  process.exit(1);
}
const body = Buffer.alloc(node.size);
fs.readSync(fd, body, 0, node.size, base + Number(node.offset));
process.stdout.write(body);
