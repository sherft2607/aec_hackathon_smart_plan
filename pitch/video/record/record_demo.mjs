// Records the end-to-end 4site demo with Playwright: a visible cursor clicks through the real app (light
// theme), while a CDP screencast saves every frame with its timestamp. Step markers go to markers.json so
// the Remotion edit can cut, zoom and caption each step.
//
//   node record/record_demo.mjs            # record into public/demo/
//   DRY=1 node record/record_demo.mjs      # screenshot each step into /tmp/demo_dry instead
//
// Needs the API on :8000 (with ANTHROPIC_API_KEY for live chat) and the web app on APP_URL.
import { spawnSync } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BASE = process.env.APP_URL ?? "http://localhost:5180";
const DRY = process.env.DRY === "1";
const OUT = DRY ? "/tmp/demo_dry" : path.join(HERE, "../public/demo");
const FRAMES = path.join(HERE, "../.frames");
const VIEW = { width: 1600, height: 900 };
const SCALE = 1.2; // 1920 x 1080 frames

const CURSOR = `
(() => {
  const install = () => {
    if (document.getElementById("__demo_cursor")) return;
    const style = document.createElement("style");
    style.textContent = \`
      #__demo_cursor { position: fixed; left: 0; top: 0; width: 26px; height: 26px; z-index: 2147483647;
        pointer-events: none; transform: translate(-100px, -100px); transition: transform 16ms linear;
        filter: drop-shadow(0 2px 3px rgba(0,0,0,.35)); }
      .__demo_ripple { position: fixed; z-index: 2147483646; pointer-events: none; width: 44px; height: 44px;
        margin: -22px 0 0 -22px; border-radius: 50%; border: 3px solid rgba(74,108,247,.9);
        background: rgba(74,108,247,.18); animation: __demo_ripple 600ms ease-out forwards; }
      @keyframes __demo_ripple { from { transform: scale(.3); opacity: 1 } to { transform: scale(1.5); opacity: 0 } }
    \`;
    document.head.appendChild(style);
    const c = document.createElement("div");
    c.id = "__demo_cursor";
    c.innerHTML = '<svg viewBox="0 0 24 24" width="26" height="26"><path d="M4 2l15 11.2-6.6.9 3.9 7.4-2.9 1.5-3.9-7.5L4 20z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.body.appendChild(c);
    window.addEventListener("mousemove", (e) => { c.style.transform = \`translate(\${e.clientX - 3}px, \${e.clientY - 2}px)\`; }, true);
    window.addEventListener("mousedown", (e) => {
      const r = document.createElement("div");
      r.className = "__demo_ripple";
      r.style.left = e.clientX + "px";
      r.style.top = e.clientY + "px";
      document.body.appendChild(r);
      setTimeout(() => r.remove(), 700);
    }, true);
  };
  if (document.body) install(); else document.addEventListener("DOMContentLoaded", install);
})();
`;

const browser = await chromium.launch({
  headless: true,
  args: ["--use-angle=metal", "--ignore-gpu-blocklist", "--enable-gpu", "--hide-scrollbars"],
});
const context = await browser.newContext({ viewport: VIEW, deviceScaleFactor: SCALE });
await context.addInitScript(() => {
  window.sessionStorage.setItem("foresite.intro.seen", "1");
  window.localStorage.setItem("foresite.theme.v2", "light");
});
await context.addInitScript(CURSOR);
const page = await context.newPage();
page.on("console", (m) => m.type() === "error" && console.log("  console:", m.text().slice(0, 160)));

mkdirSync(OUT, { recursive: true });
const frames = [];
let cdp = null;
if (!DRY) {
  rmSync(FRAMES, { recursive: true, force: true });
  mkdirSync(FRAMES, { recursive: true });
  cdp = await context.newCDPSession(page);
  cdp.on("Page.screencastFrame", async ({ data, metadata, sessionId }) => {
    const file = path.join(FRAMES, `f${String(frames.length).padStart(6, "0")}.jpg`);
    frames.push({ file, t: metadata.timestamp });
    writeFileSync(file, Buffer.from(data, "base64"));
    await cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => undefined);
  });
}

const markers = [];
let t0 = null;
const now = () => Date.now() / 1000;
let step = 0;
async function mark(name) {
  markers.push({ name, t: now() - t0 });
  console.log(`${(now() - t0).toFixed(1).padStart(6)}s  ${name}`);
  if (DRY) await page.screenshot({ path: `${OUT}/${String(++step).padStart(2, "0")}_${name}.png` });
}
const wait = (ms) => page.waitForTimeout(ms);

let mouse = { x: VIEW.width / 2, y: VIEW.height / 2 };
async function moveTo(x, y, ms = 650) {
  const steps = Math.max(8, Math.round(ms / 16));
  const from = { ...mouse };
  for (let i = 1; i <= steps; i++) {
    const k = i / steps;
    const e = k < 0.5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2;
    await page.mouse.move(from.x + (x - from.x) * e, from.y + (y - from.y) * e);
  }
  mouse = { x, y };
}
async function point(locator, { ms = 650, dx = 0.5, dy = 0.5 } = {}) {
  await locator.scrollIntoViewIfNeeded({ timeout: 15000 }).catch(() => undefined);
  const box = await locator.boundingBox({ timeout: 15000 });
  if (!box) throw new Error(`no box for ${locator}`);
  await moveTo(box.x + box.width * dx, box.y + box.height * dy, ms);
  return box;
}
async function click(locator, opts = {}) {
  await point(locator, opts);
  await wait(opts.hover ?? 250);
  await page.mouse.down();
  await wait(70);
  await page.mouse.up();
  await wait(opts.after ?? 600);
}
async function scrollIn(locator, dy, times = 6) {
  await point(locator, { ms: 400 });
  for (let i = 0; i < times; i++) {
    await page.mouse.wheel(0, dy / times);
    await wait(60);
  }
}

const panel = page.locator(".fs-shell__right .fs-site, .fs-shell__right [class*='fs-site']").first();
const tab = (name) => page.getByRole("tab", { name }).or(page.locator(".fs-site__bar button", { hasText: name })).first();

// ---- The flow ----------------------------------------------------------------------------------------
const right = page.locator(".fs-shell__right");
async function maybe(locator, opts) {
  if (await locator.count()) await click(locator.first(), opts);
  else console.log("  missing:", String(locator));
}
await page.goto(BASE);
await page.waitForSelector(".fs-topbar", { state: "visible" });
await wait(6000);
if (cdp) await cdp.send("Page.startScreencast", { format: "jpeg", quality: 90, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 });
t0 = now();
await moveTo(820, 520, 10);
await wait(1500);
await mark("city");

// Search
await click(page.locator(".fs-search"), { after: 500 });
await mark("search_open");
await page.keyboard.type("861 Park Ave Brooklyn", { delay: 75 });
const result = page.locator(".fs-cmd__item", { hasText: /861 Park Ave.*Brooklyn/i }).first();
await result.waitFor({ timeout: 30000 });
await wait(800);
await click(result, { after: 200 });
await mark("fly_to");
await right.getByText("Watch out for", { exact: false }).first().waitFor({ timeout: 60000 });
await wait(5000);
await mark("similar");

// Watch out for: the risk most similar projects share, and its checklist items
const risk = right.locator(".fs-watch__risk").first();
await point(risk, { ms: 700 });
await wait(900);
await click(risk, { after: 1200 });
await mark("watch_items");
await moveTo(1400, 560, 800);
await wait(4500);
await click(risk, { after: 600 });

// The past case: strand on the map, then its lessons
const hero = right.locator(".fs-case", { hasText: /211 E 34th/i }).first();
await point(hero, { ms: 700 });
await wait(700);
await click(hero, { after: 600, dy: 0.3 });
await mark("case_strand");
await wait(4500);
await click(hero.locator(".fs-case__open"), { after: 1500 });
await mark("case_dialog");
await wait(2500);
const dialog = page.locator(".fs-case-dialog");
await scrollIn(dialog, 420, 8);
await wait(3500);
await scrollIn(dialog, 420, 8);
await wait(3500);
await mark("case_dialog_end");
await click(page.locator(".fs-case-dialog__close"), { after: 1800 });

// This lot: top signals and early warnings
await click(tab(/This lot/), { after: 1500 });
await mark("this_lot");
await wait(2500);
const warnings = right.locator(".fs-site__section", { hasText: "Early warnings" }).first();
await warnings.scrollIntoViewIfNeeded().catch(() => undefined);
await wait(800);
await point(warnings, { ms: 600, dy: 0.15 });
await mark("early_warnings");
await wait(2500);
const warnCard = warnings.locator(".fs-card").first();
if (await warnCard.count()) {
  await maybe(warnCard.locator(".fs-explain summary"), { after: 1200 });
  await mark("warning_why");
  await wait(3500);
}

// Start a project from what you'd do here
await click(tab(/Similar projects/), { after: 1200 });
const lessons = right.locator(".fs-lessons");
await maybe(lessons.getByRole("button", { name: /^New build$/ }), { after: 1000 });
await maybe(lessons.locator(".fs-lessons__scopes").getByRole("button", { name: /Excavation/i }), { after: 1200 });
await mark("option_picked");
await wait(1500);
const start = right.locator(".fs-lessons__start");
await start.scrollIntoViewIfNeeded().catch(() => undefined);
await click(start, { after: 2500 });
await mark("project_setup");
await wait(2500);
const known = page.locator(".fs-ps-known");
if (await known.count()) { await point(known, { ms: 700 }); await wait(3500); await mark("known_facts"); }
await maybe(page.locator(".fs-ps-card", { hasText: "Masonry" }), { after: 800 });
const deep = page.locator(".fs-ps-chips[aria-label='How deep will you dig?'] .fs-chip");
if (await deep.count()) await click(deep.nth(Math.min(1, (await deep.count()) - 1)), { after: 700 });
const storeys = page.locator(".fs-ps-input").first();
if (await storeys.count()) { await click(storeys, { after: 200 }); await page.keyboard.type("6", { delay: 120 }); await wait(600); }
await mark("project_filled");
await wait(1200);
await click(page.getByRole("button", { name: /Draft checklist/i }), { after: 2500 });
await page.locator(".fs-ps-row").first().waitFor({ timeout: 40000 }).catch(() => console.log("  no checklist rows"));
await wait(1500);
await maybe(page.locator(".fs-ps-notice .fs-linkbtn", { hasText: /Got it|Dismiss/ }), { after: 600 });
await mark("checklist");
await wait(3000);
const tl = page.locator(".fs-ps-tl");
if (await tl.count()) { await point(tl, { ms: 700 }); await wait(2500); await mark("timeline"); }
const row = page.locator(".fs-ps-row", { hasText: /adjoining/i }).first();
const pick = (await row.count()) ? row : page.locator(".fs-ps-row").first();
await point(pick, { ms: 700 });
await wait(1500);
await mark("checklist_row");
const trail = pick.locator(".fs-ps-trail .fs-linkbtn");
if (await trail.count()) { await click(trail.first(), { after: 2500 }); await mark("trail"); }
await click(pick.locator(".fs-ps-check"), { after: 1800 });
await mark("checklist_status");
const objection = page.locator(".fs-ps-row", { hasText: /objection/i }).first();
if (await objection.count()) {
  await objection.scrollIntoViewIfNeeded();
  await wait(600);
  await point(objection, { ms: 700 });
  await wait(4000);
  await mark("objection_row");
} else console.log("  no objection row");
await scrollIn(page.locator(".fs-ps__body"), 700, 10);
await wait(2500);
await mark("checklist_scrolled");
await click(page.getByRole("button", { name: /← Map/ }), { after: 2500 });
await mark("back_to_map");

// Chat
const input = page.locator(".fs-shell__chat textarea").first();
await click(input, { after: 400 });
await mark("chat_open");
await page.keyboard.type("What should the structural engineer check before excavation continues?", { delay: 38 });
await wait(600);
await page.keyboard.press("Enter");
await mark("chat_sent");
await page.waitForFunction(() => {
  const l = document.querySelector("[role='log'][aria-label='Questions and answers']");
  return l && l.querySelector("article") && !/Looking this up/.test(l.textContent ?? "");
}, null, { timeout: 180000 }).catch(() => console.log("  chat: still waiting"));
await mark("chat_answer");
await wait(6000);
await mark("chat_full");
const log = page.locator("[role='log'][aria-label='Questions and answers']");
for (let i = 0; i < 5; i++) {
  await scrollIn(log, 170, 8);
  await wait(1400);
}
await mark("chat_scrolled");

// Limitations, always visible
await maybe(page.locator(".fs-limits__head"), { after: 1500 });
await mark("limitations");
await wait(3500);
await mark("end");

if (cdp) {
  await cdp.send("Page.stopScreencast");
  await wait(500);
}
await browser.close();

writeFileSync(path.join(OUT, "markers.json"), JSON.stringify(markers, null, 2));
if (!DRY && frames.length) {
  // Variable-rate screencast frames into a constant 30 fps video.
  const start = frames[0].t;
  const lines = ["ffconcat version 1.0"];
  frames.forEach((f, i) => {
    const next = frames[i + 1]?.t ?? f.t + 0.5;
    lines.push(`file '${f.file}'`, `duration ${Math.max(0.001, next - f.t).toFixed(4)}`);
  });
  lines.push(`file '${frames.at(-1).file}'`);
  writeFileSync(path.join(FRAMES, "list.ffconcat"), lines.join("\n"));
  const offset = start - (t0 ?? start);
  writeFileSync(path.join(OUT, "markers.json"), JSON.stringify(markers.map((m) => ({ ...m, t: +(m.t - offset).toFixed(3) })), null, 2));
  const r = spawnSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", path.join(FRAMES, "list.ffconcat"),
    "-vf", "fps=30,scale=1920:1080:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-preset", "slow", "-crf", "16",
    path.join(OUT, "demo.mp4")], { stdio: "inherit" });
  console.log("frames", frames.length, "ffmpeg", r.status);
}
