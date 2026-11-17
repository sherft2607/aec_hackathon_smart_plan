// Inputs, process, outputs: the whole system as one animated diagram, with records flowing through it.
import { interpolate, useCurrentFrame } from "remotion";

import { C, GROTESK, PIXEL } from "../theme";
import { Eyebrow, Headline, Slide } from "../ui";

type Node = { id: string; x: number; y: number; w: number; t: string; s?: string; tone?: "blue" | "dark" };

const IN: Node[] = [
  { id: "addr", x: 110, y: 330, w: 420, t: "An address or a click", s: "GeoSearch → lot (BBL) and building" },
  { id: "proj", x: 110, y: 450, w: 420, t: "The project", s: "work type · structure · scope · role" },
  { id: "rec", x: 110, y: 570, w: 420, t: "Public records", s: "DOB filings, complaints, violations, 311" },
  { id: "ground", x: 110, y: 690, w: 420, t: "Ground and weather", s: "soil · bedrock · flood · rain, freeze-thaw" },
  { id: "geo", x: 110, y: 810, w: 420, t: "3D city", s: "Cityweft buildings · PLUTO · footprints" },
];
const MID: Node[] = [
  { id: "profile", x: 750, y: 360, w: 430, t: "Site profile", s: "the lot + every lot it touches", tone: "dark" },
  { id: "sim", x: 750, y: 500, w: 430, t: "Similarity", s: "weighted features vs 42 past cases", tone: "blue" },
  { id: "rules", x: 750, y: 640, w: 430, t: "Early-warning rules", s: "record sequences in time", tone: "blue" },
  { id: "chat", x: 750, y: 780, w: 430, t: "Claude, cited", s: "every answer cites its source record", tone: "blue" },
];
const OUT: Node[] = [
  { id: "map", x: 1400, y: 330, w: 410, t: "Site on the 3D map", s: "with its neighbors highlighted" },
  { id: "cases", x: 1400, y: 450, w: 410, t: "Similar cases", s: "what matched, what happened" },
  { id: "warn", x: 1400, y: 570, w: 410, t: "Early warnings", s: "each with source and date" },
  { id: "list", x: 1400, y: 690, w: 410, t: "Role checklist", s: "code section · proof needed" },
  { id: "ans", x: 1400, y: 810, w: 410, t: "Answers + limits", s: "pinned to the project" },
];
const H = 92;

const EDGES: [string, string][] = [
  ["addr", "profile"], ["proj", "profile"], ["rec", "profile"], ["ground", "profile"], ["geo", "profile"],
  ["profile", "sim"], ["profile", "rules"], ["profile", "chat"], ["rec", "rules"], ["ground", "rules"],
  ["profile", "map"], ["sim", "cases"], ["rules", "warn"], ["proj", "list"], ["rules", "list"], ["chat", "ans"],
];

const ALL = [...IN, ...MID, ...OUT];
const byId = Object.fromEntries(ALL.map((n) => [n.id, n]));
const colOf = (id: string) => (IN.some((n) => n.id === id) ? 0 : MID.some((n) => n.id === id) ? 1 : 2);
const START = [30, 90, 160];

function path(a: Node, b: Node) {
  if (colOf(a.id) === colOf(b.id)) {
    const x = a.x + 20;
    return `M${x},${a.y + H} L${x},${b.y}`;
  }
  const x1 = a.x + a.w, y1 = a.y + H / 2, x2 = b.x, y2 = b.y + H / 2, mx = (x1 + x2) / 2;
  return `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`;
}

function bezierPoint(a: Node, b: Node, t: number) {
  if (colOf(a.id) === colOf(b.id)) return { x: a.x + 20, y: a.y + H + (b.y - a.y - H) * t };
  const x1 = a.x + a.w, y1 = a.y + H / 2, x2 = b.x, y2 = b.y + H / 2, mx = (x1 + x2) / 2;
  const u = 1 - t;
  return {
    x: u ** 3 * x1 + 3 * u * u * t * mx + 3 * u * t * t * mx + t ** 3 * x2,
    y: u ** 3 * y1 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t ** 3 * y2,
  };
}

export function Flow({ duration }: { duration: number }) {
  const frame = useCurrentFrame();
  const appear = (n: Node, i: number) => interpolate(frame, [START[colOf(n.id)] + i * 5, START[colOf(n.id)] + i * 5 + 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <Slide section="How it works" index={5} duration={duration}>
      <div style={{ position: "absolute", left: 110, top: 80 }}>
        <Eyebrow>Inputs → process → outputs</Eyebrow>
        <Headline delay={4} size={60} style={{ marginTop: 14 }} lines={[["Public", "data", "in.", { t: "Risk", color: C.blue }, { t: "intelligence", color: C.blue }, "out."]]} />
      </div>
      {["Inputs", "Process", "Outputs"].map((t, i) => (
        <div key={t} style={{ position: "absolute", left: [110, 750, 1400][i], top: 270, fontFamily: PIXEL, fontSize: 20, letterSpacing: "0.2em", color: C.ink2, opacity: interpolate(frame, [START[i] - 10, START[i]], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
          {t.toUpperCase()}
        </div>
      ))}
      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
        {EDGES.map(([a, b], i) => {
          const A = byId[a], B = byId[b];
          const start = Math.max(START[colOf(a)], START[colOf(b)]) + 10 + i * 2;
          const p = interpolate(frame, [start, start + 26], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return <path key={i} d={path(A, B)} fill="none" stroke={C.ink} strokeWidth={2.5} pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - p} opacity={0.55} />;
        })}
        {EDGES.map(([a, b], i) => {
          const start = Math.max(START[colOf(a)], START[colOf(b)]) + 40;
          if (frame < start) return null;
          return [0, 0.5].map((off) => {
            const t = ((frame - start) / 60 + off + i * 0.13) % 1;
            const pt = bezierPoint(byId[a], byId[b], t);
            return <rect key={`${i}-${off}`} x={pt.x - 5} y={pt.y - 5} width={10} height={10} fill={colOf(b) === 2 ? C.blue : C.red} />;
          });
        })}
      </svg>
      {ALL.map((n) => {
        const list = colOf(n.id) === 0 ? IN : colOf(n.id) === 1 ? MID : OUT;
        const p = appear(n, list.indexOf(n));
        const dark = n.tone === "dark", blue = n.tone === "blue";
        return (
          <div key={n.id} style={{ position: "absolute", left: n.x, top: n.y, width: n.w, height: H, boxSizing: "border-box", padding: "14px 20px", border: `3px solid ${C.ink}`, background: dark ? C.ink : blue ? "#e6ebff" : C.card, color: dark ? "#fff" : C.ink, boxShadow: `${6 * p}px ${6 * p}px 0 ${C.ink}`, opacity: p, transform: `translateY(${(1 - p) * 20}px)`, fontFamily: GROTESK }}>
            <div style={{ fontSize: 27, fontWeight: 700 }}>{n.t}</div>
            <div style={{ fontSize: 19, marginTop: 4, color: dark ? "rgba(255,255,255,0.75)" : C.ink2 }}>{n.s}</div>
          </div>
        );
      })}
    </Slide>
  );
}
