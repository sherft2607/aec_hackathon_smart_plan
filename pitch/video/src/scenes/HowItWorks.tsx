// How the three engines work: similarity (the real weights and the demo's real comparison), the
// early-warning rules (record sequences in time), and the grounded chat.
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";

import { C, PIXEL } from "../theme";
import { Eyebrow, HardCard, Headline, PixelLabel, Reveal, Slide } from "../ui";

export const HOW_BEATS = { sim: 0, warn: 400, list: 400, chat: 760 };

function Beat({ from, to, children }: { from: number; to: number; children: React.ReactNode }) {
  const frame = useCurrentFrame();
  if (frame < from - 1 || frame > to + 1) return null;
  const o = Math.min(
    from === 0 ? 1 : interpolate(frame, [from, from + 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
    interpolate(frame, [to - 12, to], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
  );
  return <AbsoluteFill style={{ opacity: o }}>{children}</AbsoluteFill>;
}

const WEIGHTS = [
  { g: "The neighbor building", k: "era", w: 20 },
  { g: "", k: "wall system", w: 18 },
  { g: "", k: "height", w: 12 },
  { g: "", k: "attached", w: 10 },
  { g: "The work and the ground", k: "earth work", w: 20 },
  { g: "", k: "other work types", w: 8 },
  { g: "", k: "record hazards", w: 4 },
  { g: "", k: "soil", w: 4 },
  { g: "", k: "flood zone", w: 4 },
];

const ROWS: { k: string; mark: "✓" | "—" | "0"; pts: number; t: string }[] = [
  { k: "wall system", mark: "✓", pts: 18, t: "masonry bearing wall next door" },
  { k: "attached", mark: "✓", pts: 10, t: "attached, like the case’s building" },
  { k: "earth work", mark: "✓", pts: 20, t: "excavation on both sites" },
  { k: "record hazards", mark: "✓", pts: 4, t: "geotech enforcement records here" },
  { k: "other work types", mark: "0", pts: 0, t: "no overlap" },
  { k: "era", mark: "—", pts: 0, t: "not reported for the case: no match, not a difference (near misses earn half)" },
  { k: "soil", mark: "—", pts: 0, t: "not on record here" },
];

function Similarity() {
  const frame = useCurrentFrame();
  const rowAt = (i: number) => 120 + i * 24;
  const lit = (k: string) => ROWS.findIndex((r) => r.k === k && r.mark === "✓");
  const score = ROWS.reduce((n, r, i) => n + (frame >= rowAt(i) + 8 ? r.pts : 0), 0);
  const ring = interpolate(score, [0, 100], [0, 1]);
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 120, top: 90 }}>
        <Eyebrow>How similarity works</Eyebrow>
        <Headline delay={4} size={60} style={{ marginTop: 14 }} lines={[["A", "weighted", "sum", "of", "facts", "an", "engineer", "can", "check"]]} />
      </div>
      <div style={{ position: "absolute", left: 120, top: 260, width: 700 }}>
        {WEIGHTS.map((w, i) => {
          const grow = interpolate(frame, [20 + i * 5, 50 + i * 5], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          const li = lit(w.k);
          const on = li >= 0 && frame >= rowAt(li);
          return (
            <div key={w.k}>
              {w.g && <PixelLabel size={17} style={{ marginTop: i ? 22 : 0, marginBottom: 8 }}>{w.g}</PixelLabel>}
              <div style={{ display: "flex", alignItems: "center", gap: 16, height: 52 }}>
                <div style={{ width: 230, fontSize: 26, fontWeight: on ? 700 : 400 }}>{w.k}</div>
                <div style={{ height: 26, width: w.w * 18 * grow, background: on ? C.blue : C.ink, opacity: on ? 1 : 0.8, boxShadow: on ? `4px 4px 0 ${C.ink}` : "none" }} />
                <div style={{ fontFamily: PIXEL, fontSize: 20, opacity: grow }}>{w.w}</div>
              </div>
            </div>
          );
        })}
      </div>
      <HardCard delay={96} style={{ position: "absolute", left: 960, top: 250, width: 840, padding: "26px 30px" }}>
        <PixelLabel>861 Park Ave, Brooklyn ↔ past case</PixelLabel>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8 }}>
          <div>
            <div style={{ fontSize: 34, fontWeight: 700 }}>211 E 34th St, Manhattan · 2020</div>
            <div style={{ fontSize: 22, color: C.ink2, marginTop: 4 }}>Partial collapse next to an excavation · no injuries reported</div>
          </div>
          <svg width={130} height={130} viewBox="0 0 130 130">
            <circle cx={65} cy={65} r={54} fill="none" stroke={C.paperLine} strokeWidth={12} />
            <circle cx={65} cy={65} r={54} fill="none" stroke={C.blue} strokeWidth={12} pathLength={1} strokeDasharray={`${ring} 1`} transform="rotate(-90 65 65)" />
            <text x={65} y={70} textAnchor="middle" fontSize={40} fontWeight={700} fill={C.ink}>{score}</text>
            <text x={65} y={96} textAnchor="middle" fontFamily={PIXEL} fontSize={14} letterSpacing="1" fill={score >= 50 ? C.blue : C.muted}>{score >= 50 ? "STRONG" : score >= 35 ? "SOME" : "WEAK"}</text>
          </svg>
        </div>
        <div style={{ marginTop: 14 }}>
          {ROWS.map((r, i) => (
            <Reveal key={r.k} delay={rowAt(i)} x={20} y={0}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 16, fontSize: 24, padding: "9px 0", borderTop: `2px solid ${C.paperLine}`, color: r.mark === "✓" ? C.ink : C.muted }}>
                <span style={{ width: 28, fontWeight: 700, color: r.mark === "✓" ? C.blue : C.muted }}>{r.mark}</span>
                <span style={{ width: 200, fontWeight: 700 }}>{r.k}</span>
                <span style={{ flex: 1 }}>{r.t}</span>
                <span style={{ fontFamily: PIXEL, fontSize: 19, color: r.pts ? C.blue : C.muted }}>{r.pts ? `+${r.pts}` : "·"}</span>
              </div>
            </Reveal>
          ))}
        </div>
      </HardCard>
      <Reveal delay={300} style={{ position: "absolute", left: 960, top: 905, width: 840 }}>
        <PixelLabel color={C.ink} size={17} style={{ lineHeight: 1.6 }}>Relative to similar sites · never a prediction of failure</PixelLabel>
      </Reveal>
    </AbsoluteFill>
  );
}

const RULES = [
  { a: "Adjacent-protection violation", gap: "21 days", b: "no DOB record on that lot", found: false },
  { a: "Stop-work order", gap: "then", b: "violation for continuing work", found: true },
  { a: "Earth-work filing next door", gap: "≤ 90 days", b: "structural complaint (30, 14, 16, 5C)", found: false },
  { a: "Open excavation", gap: "during", b: "heavy rain or freeze-thaw", found: true },
];

function Warnings() {
  const frame = useCurrentFrame();
  const L = frame - HOW_BEATS.warn;
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 120, top: 90 }}>
        <Eyebrow color={C.red} delay={HOW_BEATS.warn}>How early warnings work</Eyebrow>
        <Headline delay={HOW_BEATS.warn + 4} size={60} style={{ marginTop: 14 }} lines={[["Patterns", "in", "time,", "across", "the", "lot", "line"]]} />
      </div>
      <div style={{ position: "absolute", left: 120, right: 120, top: 290 }}>
        {RULES.map((r, i) => {
          const s = 14 + i * 14;
          const a = interpolate(L, [s, s + 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          const line = interpolate(L, [s + 8, s + 30], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          const b = interpolate(L, [s + 28, s + 38], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          const f = interpolate(L, [100 + i * 6, 112 + i * 6], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return (
            <div key={r.a} style={{ display: "flex", alignItems: "center", height: 130, borderTop: `2px solid ${C.paperLine}` }}>
              <div style={{ width: 470, opacity: a, padding: "16px 22px", border: `3px solid ${C.ink}`, background: C.card, fontSize: 27, fontWeight: 700 }}>{r.a}</div>
              <div style={{ width: 230, position: "relative", height: 40 }}>
                <div style={{ position: "absolute", left: 0, top: 19, height: 3, width: `${line * 100}%`, background: C.ink }} />
                <div style={{ position: "absolute", width: "100%", top: -14, textAlign: "center", fontFamily: PIXEL, fontSize: 18, opacity: line }}>{r.gap}</div>
              </div>
              <div style={{ width: 520, opacity: b, padding: "16px 22px", border: `3px solid ${C.ink}`, background: C.card, fontSize: 27, fontWeight: 700 }}>{r.b}</div>
              <div style={{ marginLeft: 40, opacity: f, transform: `scale(${0.85 + 0.15 * f})`, fontFamily: PIXEL, fontSize: 20, letterSpacing: "0.12em", padding: "12px 16px", background: r.found ? C.red : "transparent", color: r.found ? "#fff" : C.muted, border: `3px solid ${r.found ? C.red : C.paperLine}` }}>
                {r.found ? "FOUND AT 861 PARK" : "CHECKED · NONE"}
              </div>
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", left: 120, top: 860, opacity: interpolate(L, [130, 145], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
        <PixelLabel color={C.ink} size={17}>A prompt to look, not a finding · a rule that couldn’t run says so, never “zero”</PixelLabel>
      </div>
    </AbsoluteFill>
  );
}

const LANES = [
  { role: "Design", n: 6, color: C.blue },
  { role: "DOB filing", n: 6, color: "#d9822b" },
  { role: "Neighbors notified", n: 2, color: C.green },
  { role: "Survey done", n: 1, color: C.red },
  { role: "Excavation", n: 6, color: C.ink },
];

const MORE = [
  { t: "Excavation-support drawings", code: "BC 3304.4.1", proof: "Stamped SOE drawings" },
  { t: "Check the foundation drawings against objections on similar filings", code: "35 of 154 similar DOB NOW filings held", proof: "A review noted on the project" },
];

function Checklist() {
  const frame = useCurrentFrame();
  const L = frame - HOW_BEATS.list;
  const at = (a: number, b = a + 12) => interpolate(L, [a, b], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const inputs = ["New construction · masonry", "Excavation · foundation · SOE", "Uploaded plans and geotech reports"];
  const status = L > 150 ? "In progress" : "Open";
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 120, top: 90 }}>
        <Eyebrow delay={HOW_BEATS.list}>How the checklist works</Eyebrow>
        <Headline delay={HOW_BEATS.list + 4} size={60} style={{ marginTop: 14 }} lines={[["One", "live", "checklist,", "by", "milestone,", "with", "the", { t: "proof", color: C.blue }, { t: "each", color: C.blue }, { t: "item", color: C.blue }, { t: "needs", color: C.blue }]]} />
      </div>
      <div style={{ position: "absolute", left: 120, top: 270, width: 520 }}>
        <PixelLabel size={17} style={{ opacity: at(6) }}>The project · updates with every uploaded document</PixelLabel>
        {inputs.map((t, i) => (
          <div key={t} style={{ marginTop: 12, padding: "12px 18px", border: `3px solid ${C.ink}`, background: C.card, fontSize: 24, opacity: at(10 + i * 8), transform: `translateX(${(1 - at(10 + i * 8)) * -20}px)` }}>{t}</div>
        ))}
        <div style={{ height: 50, width: 3, background: C.ink, margin: "0 auto", transform: `scaleY(${at(40, 56)})`, transformOrigin: "top" }} />
        <div style={{ display: "flex", gap: 14, opacity: at(54) }}>
          <div style={{ flex: 1, padding: "16px 18px", background: C.ink, color: "#fff", border: `3px solid ${C.ink}` }}>
            <div style={{ fontSize: 40, fontWeight: 700 }}>21</div>
            <div style={{ fontSize: 20, marginTop: 4, color: "rgba(255,255,255,0.8)" }}>items for this project, each with an owner</div>
          </div>
          <div style={{ flex: 1, padding: "16px 18px", background: "#e6ebff", border: `3px solid ${C.ink}` }}>
            <div style={{ fontSize: 40, fontWeight: 700 }}>4</div>
            <div style={{ fontSize: 20, marginTop: 4, color: C.ink2 }}>sources · code duties, hazard rules, lessons from similar projects, DOB NOW objections</div>
          </div>
        </div>
      </div>
      <div style={{ position: "absolute", left: 720, top: 270, width: 1080 }}>
        <div style={{ display: "flex", gap: 22, opacity: at(70) }}>
          {LANES.map((l, i) => (
            <div key={l.role} style={{ flex: l.n + 6, borderTop: `8px solid ${l.color}`, paddingTop: 10, transform: `scaleX(${at(70 + i * 6, 90 + i * 6)})`, transformOrigin: "left" }}>
              <div style={{ fontSize: 21, fontWeight: 700, lineHeight: 1.2 }}>{l.role}</div>
              <div style={{ fontFamily: PIXEL, fontSize: 18, color: C.ink2, marginTop: 4 }}>{l.n} items</div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 26, border: `3px solid ${C.ink}`, borderLeft: `10px solid #d9822b`, background: C.card, boxShadow: `${10 * at(96)}px ${10 * at(96)}px 0 ${C.ink}`, padding: "22px 28px", opacity: at(92), transform: `translateY(${(1 - at(92)) * 24}px)` }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <span style={{ fontSize: 34, fontWeight: 700 }}>Examine the adjoining building</span>
            <span style={{ fontFamily: PIXEL, fontSize: 15, color: C.red, border: `2px solid ${C.red}`, padding: "4px 8px" }}>LIFE SAFETY</span>
            <span style={{ marginLeft: "auto", fontSize: 22, fontWeight: 700, padding: "6px 14px", border: `3px solid ${C.ink}`, background: status === "Open" ? C.card : "#fff3d6" }}>{status}</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "180px 1fr", rowGap: 10, marginTop: 18, fontSize: 24 }}>
            {[["Owner", "Structural engineer"], ["Code", "2022 NYC BC 3309.3"], ["Proof needed", "Dated inspection records"]].map(([k, v], i) => (
              <div key={k} style={{ display: "contents" }}>
                <span style={{ fontFamily: PIXEL, fontSize: 17, color: C.ink2, alignSelf: "center", opacity: at(110 + i * 10) }}>{k.toUpperCase()}</span>
                <span style={{ fontWeight: i === 2 ? 700 : 400, color: i === 2 ? C.blue : C.ink, opacity: at(110 + i * 10) }}>{v}</span>
              </div>
            ))}
          </div>
        </div>
        {MORE.map((m, i) => (
          <div key={m.t} style={{ display: "flex", alignItems: "baseline", gap: 18, marginTop: 14, padding: "14px 28px", border: `3px solid ${C.ink}`, borderLeft: `10px solid #d9822b`, background: C.card, fontSize: 22, opacity: at(160 + i * 10) }}>
            <span style={{ fontWeight: 700, width: 420 }}>{m.t}</span>
            <span style={{ color: C.ink2, width: 280 }}>{m.code}</span>
            <span style={{ color: C.blue }}>{m.proof}</span>
          </div>
        ))}
      </div>
      <div style={{ position: "absolute", left: 120, top: 900, opacity: at(200) }}>
        <PixelLabel color={C.ink} size={17}>Not exhaustive · proof comes from the team, never from public data · shared by every role on the project</PixelLabel>
      </div>
    </AbsoluteFill>
  );
}

const CHAIN = [
  { t: "Your question", s: "“What should the SE check before excavation continues?”" },
  { t: "Claude + tools", s: "searches this site’s records, past cases, warnings, action items" },
  { t: "Every claim cites a record", s: "numbers must be in the source; no verdicts, blame, predictions or names" },
  { t: "Labeled answer", s: "public record · case library · warning · action item, with dates" },
];

function Chat() {
  const frame = useCurrentFrame();
  const L = frame - HOW_BEATS.chat;
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 120, top: 90 }}>
        <Eyebrow delay={HOW_BEATS.chat}>How the chat stays grounded</Eyebrow>
        <Headline delay={HOW_BEATS.chat + 4} size={60} style={{ marginTop: 14 }} lines={[["Plain", "English,", "every", "line", "sourced"]]} />
      </div>
      <div style={{ position: "absolute", left: 120, right: 120, top: 320, display: "flex", gap: 44 }}>
        {CHAIN.map((c, i) => {
          const p = interpolate(L, [12 + i * 18, 26 + i * 18], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return (
            <div key={c.t} style={{ flex: 1, position: "relative", opacity: p, transform: `translateY(${(1 - p) * 24}px)` }}>
              <div style={{ border: `3px solid ${C.ink}`, background: i === 2 ? C.ink : i === 3 ? "#e6ebff" : C.card, color: i === 2 ? "#fff" : C.ink, padding: "30px 30px", minHeight: 400, boxSizing: "border-box", boxShadow: `8px 8px 0 ${C.ink}` }}>
                <PixelLabel color={i === 2 ? "rgba(255,255,255,0.7)" : C.ink2} size={22}>{String(i + 1).padStart(2, "0")}</PixelLabel>
                <div style={{ fontSize: 38, fontWeight: 700, marginTop: 18, lineHeight: 1.15 }}>{c.t}</div>
                <div style={{ fontSize: 28, lineHeight: 1.35, marginTop: 16, color: i === 2 ? "rgba(255,255,255,0.8)" : C.ink2 }}>{c.s}</div>
              </div>
              {i < 3 && <div style={{ position: "absolute", right: -44, top: 200, width: 44 * p, height: 3, background: C.ink }} />}
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", left: 120, top: 800, opacity: interpolate(L, [90, 105], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
        <PixelLabel color={C.ink} size={17}>A claim that fails a check is held back and the answer says so · not engineering advice</PixelLabel>
      </div>
    </AbsoluteFill>
  );
}

export function HowItWorks({ duration }: { duration: number }) {
  return (
    <Slide section="How it works" index={6} duration={duration}>
      <Beat from={0} to={HOW_BEATS.list}>
        <Similarity />
      </Beat>
      <Beat from={HOW_BEATS.list} to={HOW_BEATS.chat}>
        <Checklist />
      </Beat>
      <Beat from={HOW_BEATS.chat} to={duration + 20}>
        <Chat />
      </Beat>
    </Slide>
  );
}
