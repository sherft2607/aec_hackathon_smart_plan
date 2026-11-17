// The solution in one line and four steps, on the deck's dark slide.
import { interpolate, useCurrentFrame } from "remotion";

import { C } from "../theme";
import { Eyebrow, HardCard, Headline, PixelLabel, Reveal, Slide } from "../ui";

const STEPS = [
  { n: "01", t: "Pick a site", d: "Search any NYC address or click a building on the 3D map." },
  { n: "02", t: "See the public record", d: "Filings, complaints, violations, ground and flood: on this lot and the lots it touches." },
  { n: "03", t: "Compare similar cases", d: "Past NYC sites with the same profile, and what happened there." },
  { n: "04", t: "Act on early warnings", d: "Record patterns worth a look, and a checklist for your role and stage." },
];

export function Solution({ duration }: { duration: number }) {
  const frame = useCurrentFrame();
  return (
    <Slide dark section="Solution" index={4} duration={duration}>
      <div style={{ position: "absolute", left: 120, top: 110, width: 1500 }}>
        <Eyebrow color="#8fa5ff">The solution · 4site</Eyebrow>
        <Headline delay={4} size={84} style={{ marginTop: 18 }}
          lines={[["One", "risk-intelligence", "map"], ["for", "every", "site", "in", { t: "New", color: "#8fa5ff" }, { t: "York.", color: "#8fa5ff" }]]} />
      </div>
      <div style={{ position: "absolute", left: 120, right: 120, top: 470, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 34 }}>
        {STEPS.map((s, i) => {
          const lit = interpolate(frame, [60 + i * 30, 75 + i * 30], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return (
            <HardCard key={s.n} dark delay={40 + i * 8} style={{ minHeight: 300, position: "relative", borderColor: lit > 0.5 ? "#8fa5ff" : C.nightInk, background: `rgba(74,108,247,${0.22 * lit})` }}>
              <PixelLabel color={lit > 0.5 ? "#8fa5ff" : "rgba(241,239,233,0.6)"} size={26}>{s.n}</PixelLabel>
              <div style={{ fontSize: 38, fontWeight: 700, marginTop: 20 }}>{s.t}</div>
              <div style={{ fontSize: 25, lineHeight: 1.35, marginTop: 14, color: "rgba(241,239,233,0.78)" }}>{s.d}</div>
              {i < 3 && (
                <div style={{ position: "absolute", right: -34, top: 140, width: 34 * lit, height: 3, background: "#8fa5ff" }} />
              )}
            </HardCard>
          );
        })}
      </div>
      <Reveal delay={190} style={{ position: "absolute", left: 120, top: 900 }}>
        <PixelLabel color="rgba(241,239,233,0.7)" size={20}>NYC first · every fact with its source and date · a prompt to look, never a prediction</PixelLabel>
      </Reveal>
    </Slide>
  );
}
