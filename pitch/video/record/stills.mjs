// Renders review stills: node record/stills.mjs Scene-Team:120 Scene-Problem:200 ... (into /tmp/stills).
import { mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const out = process.env.OUT ?? "/tmp/stills";
mkdirSync(out, { recursive: true });
const serveUrl = await bundle({ entryPoint: path.join(root, "src/index.ts"), publicDir: path.join(root, "public") });
for (const arg of process.argv.slice(2)) {
  const [id, f] = arg.split(":");
  const composition = await selectComposition({ serveUrl, id });
  const file = path.join(out, `${id}_${f}.jpg`);
  await renderStill({ serveUrl, composition, frame: Number(f), output: file, imageFormat: "jpeg", jpegQuality: 80, scale: 0.5, chromiumOptions: { gl: "angle" } });
  console.log(file);
}
