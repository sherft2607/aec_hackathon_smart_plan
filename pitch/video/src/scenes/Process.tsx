// How we built it: the hackathon process as an animated path with every tool's logo, then how one
// BUILD.md fanned out to eight agent sessions and came back as merged pull requests.
import { AbsoluteFill, Img, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame } from "remotion";

import { C, PIXEL } from "../theme";
import { Eyebrow, Headline, Logo, PixelLabel, Slide } from "../ui";

export const PROCESS_SPLIT = 440;

const STEPS: { t: string; d: string; logos: string[] }[] = [
  { t: "Brainstorm", d: "three team sessions, recorded with Wispr Flow", logos: ["wispr.png"] },
  { t: "Synthesis", d: "transcripts into a vision and a build plan", logos: ["cursor.svg", "claude.svg"] },
  { t: "Plan iterations", d: "the plan rewritten after each round", logos: ["cursor.svg", "claude.svg"] },
  { t: "Concept videos", d: "clickable prototypes, recorded to video", logos: ["playwright.svg", "ffmpeg.svg"] },
  { t: "Feedback", d: "the team and a Thornton Tomasetti forensic expert", logos: [] },
  { t: "BUILD.md", d: "one source of truth: rules, contracts, PR order", logos: ["git.svg", "github.svg"] },
  { t: "Parallel build", d: "8 people, 8 agent sessions, merged in order", logos: ["cursor.svg", "claude.svg", "github.svg"] },
  { t: "Prototype review", d: "use it, give feedback, fix, record", logos: ["playwright.svg", "remotion.png"] },
];

const CARD = { w: 380, h: 200 };
const pos = (i: number) => {
  const row = i < 4 ? 0 : 1;
  const col = row === 0 ? i : 7 - i;
  return { x: 120 + col * 430, y: row === 0 ? 290 : 640 };
};
const at = (i: number) => 24 + i * 44;

function Path() {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
        {STEPS.slice(0, -1).map((_, i) => {
          const a = pos(i), b = pos(i + 1);
          const p = interpolate(frame, [at(i) + 16, at(i + 1)], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          const d = i === 3
            ? `M${a.x + CARD.w},${a.y + CARD.h / 2} C${a.x + CARD.w + 90},${a.y + CARD.h / 2} ${b.x + CARD.w + 90},${b.y + CARD.h / 2} ${b.x + CARD.w},${b.y + CARD.h / 2}`
            : a.y === b.y
              ? (b.x > a.x ? `M${a.x + CARD.w},${a.y + CARD.h / 2} L${b.x},${b.y + CARD.h / 2}` : `M${a.x},${a.y + CARD.h / 2} L${b.x + CARD.w},${b.y + CARD.h / 2}`)
              : "";
          return <path key={i} d={d} fill="none" stroke={C.ink} strokeWidth={4} pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - p} />;
        })}
        {(() => {
          const a = pos(7), b = pos(4);
          const p = interpolate(frame, [at(7) + 30, at(7) + 70], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          const d = `M${a.x + CARD.w / 2},${a.y + CARD.h} C${a.x + CARD.w / 2},${a.y + CARD.h + 110} ${b.x + CARD.w / 2},${b.y + CARD.h + 110} ${b.x + CARD.w / 2},${b.y + CARD.h}`;
          return (
            <g>
              <path d={d} fill="none" stroke={C.blue} strokeWidth={4} pathLength={1} strokeDasharray="0.012 0.012" opacity={p} />
              <text x={(a.x + b.x + CARD.w) / 2} y={a.y + CARD.h + 112} textAnchor="middle" fontFamily={PIXEL} fontSize={19} letterSpacing="3" fill={C.blue} opacity={p}>FEEDBACK LOOP</text>
            </g>
          );
        })()}
      </svg>
      {STEPS.map((s, i) => {
        const { x, y } = pos(i);
        const p = interpolate(frame, [at(i), at(i) + 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return (
          <div key={s.t} style={{ position: "absolute", left: x, top: y, width: CARD.w, height: CARD.h, boxSizing: "border-box", border: `3px solid ${C.ink}`, background: C.card, boxShadow: `${8 * p}px ${8 * p}px 0 ${C.ink}`, padding: "20px 24px", opacity: p, transform: `translateY(${(1 - p) * 24}px)` }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <PixelLabel color={C.blue} size={20}>{String(i + 1).padStart(2, "0")}</PixelLabel>
              <div style={{ display: "flex", gap: 10 }}>
                {s.logos.map((l) => <Logo key={l} name={l} size={40} />)}
                {!s.logos.length && <PixelLabel size={15} color={C.ink}>TT forensics</PixelLabel>}
              </div>
            </div>
            <div style={{ fontSize: 33, fontWeight: 700, marginTop: 14 }}>{s.t}</div>
            <div style={{ fontSize: 22, color: C.ink2, marginTop: 6, lineHeight: 1.3 }}>{s.d}</div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
}

function ConceptClip() {
  const frame = useCurrentFrame();
  const from = at(3) + 10;
  const p = Math.min(
    interpolate(frame, [from, from + 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
    interpolate(frame, [from + 88, from + 102], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
  );
  if (p <= 0) return null;
  return (
    <div style={{ position: "absolute", left: 120, top: 560, width: 640, height: 400, border: `3px solid ${C.ink}`, boxShadow: `10px 10px 0 ${C.ink}`, background: "#fff", opacity: p, transform: `scale(${0.9 + 0.1 * p})`, transformOrigin: "top left", overflow: "hidden" }}>
      <Sequence from={from} layout="none">
        <OffthreadVideo src={staticFile("concept_clip.mp4")} muted playbackRate={1.5} style={{ width: "100%", height: "100%" }} />
      </Sequence>
      <div style={{ position: "absolute", left: 0, bottom: 0, background: C.ink, color: "#fff", fontFamily: PIXEL, fontSize: 15, letterSpacing: "0.14em", padding: "8px 12px" }}>CONCEPT PROTOTYPE · EARLY DRAFT</div>
    </div>
  );
}

const TEAM = ["camilo", "ethnie", "hongyu", "jacob", "jahleel", "lise", "rishabh", "shandon"];
const MERGED: Record<string, number> = { jacob: 12, jahleel: 10, rishabh: 5, lise: 3, hongyu: 3, camilo: 3, ethnie: 2, shandon: 2 };

function Build() {
  const frame = useCurrentFrame();
  const L = frame - PROCESS_SPLIT;
  const fan = interpolate(L, [30, 70], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const back = interpolate(L, [90, 150], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const docLines = ["Rules", "Shared contracts", "PR order, wave by wave", "Your section: your paths"];
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 120, top: 90 }}>
        <Eyebrow delay={PROCESS_SPLIT}>How the build ran</Eyebrow>
        <Headline delay={PROCESS_SPLIT + 4} size={60} style={{ marginTop: 14 }} lines={[["One", "plan,", "eight", "agents,", { t: "41", color: C.blue }, { t: "merged", color: C.blue }, { t: "PRs", color: C.blue }]]} />
      </div>
      <div style={{ position: "absolute", left: 120, top: 330, width: 420, border: `3px solid ${C.ink}`, background: C.card, boxShadow: `10px 10px 0 ${C.ink}`, padding: 28, opacity: interpolate(L, [6, 20], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
        <div style={{ fontFamily: "monospace", fontSize: 30, fontWeight: 700 }}>BUILD.md</div>
        {docLines.map((l, i) => (
          <div key={l} style={{ fontSize: 23, marginTop: 16, color: C.ink2, opacity: interpolate(L, [14 + i * 6, 24 + i * 6], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}># {l}</div>
        ))}
        <div style={{ display: "flex", gap: 10, marginTop: 24 }}>
          <Logo name="cursor.svg" size={34} />
          <Logo name="claude.svg" size={34} />
          <span style={{ fontSize: 19, color: C.ink2, alignSelf: "center" }}>“I’m &lt;name&gt;” starts a session</span>
        </div>
      </div>
      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
        {TEAM.map((_, i) => {
          const y = 300 + i * 82 + 34;
          return (
            <g key={i}>
              <path d={`M570,560 C700,560 700,${y} 820,${y}`} fill="none" stroke={C.ink} strokeWidth={2.5} pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - fan} opacity={0.6} />
              <path d={`M1180,${y} C1260,${y} 1260,560 1320,560`} fill="none" stroke={C.blue} strokeWidth={2.5} pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - back} opacity={0.8} />
            </g>
          );
        })}
      </svg>
      {TEAM.map((id, i) => {
        const p = interpolate(L, [40 + i * 4, 52 + i * 4], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        const n = MERGED[id];
        return (
          <div key={id} style={{ position: "absolute", left: 820, top: 300 + i * 82, display: "flex", alignItems: "center", gap: 14, opacity: p }}>
            <Img src={staticFile(`team/${id}.jpg`)} style={{ width: 68, height: 68, borderRadius: "50%", border: `3px solid ${C.ink}`, filter: "grayscale(1)" }} />
            <div style={{ display: "flex", gap: 5 }}>
              {Array.from({ length: 0 * n }).map((_, k) => (
                <div key={k} style={{ width: 16, height: 26, background: C.blue, opacity: interpolate(L, [70 + k * 4, 76 + k * 4], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }} />
              ))}
            </div>
          </div>
        );
      })}
      <div style={{ position: "absolute", left: 1320, top: 360, width: 500, boxSizing: "border-box", border: `3px solid ${C.ink}`, background: C.ink, color: "#fff", boxShadow: `10px 10px 0 ${C.blue}`, padding: 30, opacity: back }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <Logo name="github.svg" size={44} style={{ filter: "invert(1)" }} />
          <div style={{ fontSize: 30, fontWeight: 700 }}>main</div>
        </div>
        {[["44", "pull requests opened"], ["41", "merged, in about 5 hours"], ["4", "waves, contracts first"], ["~102k", "lines added"]].map(([n, t]) => (
          <div key={t} style={{ display: "flex", alignItems: "baseline", gap: 14, marginTop: 14 }}>
            <span style={{ fontSize: 40, fontWeight: 700, color: "#8fa5ff", minWidth: 130 }}>{n}</span>
            <span style={{ fontSize: 22, color: "rgba(255,255,255,0.85)" }}>{t}</span>
          </div>
        ))}
        <PixelLabel color="rgba(255,255,255,0.6)" size={14} style={{ marginTop: 18, lineHeight: 1.5 }}>Conflicts reconciled with merge commits · never force-pushed</PixelLabel>
      </div>
      <PixelLabel color={C.ink} size={16} style={{ position: "absolute", left: 820, top: 970, opacity: back }}>Eight agent sessions, one per teammate</PixelLabel>
    </AbsoluteFill>
  );
}

export function Process({ duration }: { duration: number }) {
  const frame = useCurrentFrame();
  const a = interpolate(frame, [PROCESS_SPLIT - 14, PROCESS_SPLIT], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const b = interpolate(frame, [PROCESS_SPLIT, PROCESS_SPLIT + 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <Slide section="Process" index={11} duration={duration}>
      {frame < PROCESS_SPLIT + 1 && (
        <AbsoluteFill style={{ opacity: a }}>
          <div style={{ position: "absolute", left: 120, top: 90 }}>
            <Eyebrow>How we built it</Eyebrow>
            <Headline delay={4} size={60} style={{ marginTop: 14 }} lines={[["From", "a", "recorded", "brainstorm", "to", "a", "working", "product"]]} />
          </div>
          <Path />
          <ConceptClip />
        </AbsoluteFill>
      )}
      {frame >= PROCESS_SPLIT && (
        <AbsoluteFill style={{ opacity: b }}>
          <Build />
        </AbsoluteFill>
      )}
    </Slide>
  );
}
