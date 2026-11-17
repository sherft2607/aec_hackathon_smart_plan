// What 4site does not know, stated plainly, and what comes next.
import { interpolate, useCurrentFrame } from "remotion";

import { C } from "../theme";
import { Eyebrow, HardCard, Headline, PixelLabel, Reveal, Slide } from "../ui";

const LIMITS = [
  "Public records and reported cases only: records lag and can be incomplete",
  "Not a DOB determination and not engineering advice",
  "Similarity is relative to 42 past cases, never a prediction",
  "Proof comes from the team, never inferred from public data",
  "Soil, bedrock and flood are often not on record",
];

const NEXT = [
  { t: "DOB objection reasons", d: "today 4site flags scopes where similar filings sit at objections; next, what the objections were about, once DOB publishes it" },
  { t: "Forensics ledger", d: "after an event: index the documents into a dated evidence ledger the engineer confirms (from our forensic advisor)" },
  { t: "Daily pulls + alerts", d: "re-run the early-warning rules every day across the 1,187-site watchlist" },
  { t: "Read drawings and models", d: "structural system from Revit and drawing sets, not only the public record" },
  { t: "Calibrate the pattern score", d: "grow the case library and test which sequences came before incidents" },
  { t: "More cities", d: "the same engine for any city with open permits and complaints" },
];

export function Limits({ duration }: { duration: number }) {
  const frame = useCurrentFrame();
  return (
    <Slide section="Limits & next" index={10} duration={duration}>
      <div style={{ position: "absolute", left: 120, top: 90 }}>
        <Eyebrow color={C.red}>Limitations and next steps</Eyebrow>
        <Headline delay={4} size={64} style={{ marginTop: 14 }} lines={[["Honest", "about", "what", "it", "can’t", "see"]]} />
      </div>
      <HardCard delay={14} style={{ position: "absolute", left: 120, top: 270, width: 760, minHeight: 600 }}>
        <PixelLabel color={C.red} size={20}>What 4site doesn’t know</PixelLabel>
        {LIMITS.map((l, i) => (
          <Reveal key={l} delay={24 + i * 8} x={-16} y={0}>
            <div style={{ display: "flex", gap: 16, fontSize: 28, lineHeight: 1.3, marginTop: 24 }}>
              <span style={{ color: C.red, fontWeight: 700 }}>—</span>
              {l}
            </div>
          </Reveal>
        ))}
      </HardCard>
      <div style={{ position: "absolute", left: 960, top: 270, width: 840 }}>
        <PixelLabel color={C.blue} size={20}>Next</PixelLabel>
        <div style={{ position: "relative", marginTop: 18 }}>
          <div style={{ position: "absolute", left: 13, top: 10, width: 3, height: `${interpolate(frame, [80, 200], [0, 92], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}%`, background: C.blue }} />
          {NEXT.map((n, i) => (
            <Reveal key={n.t} delay={70 + i * 18} x={20} y={0}>
              <div style={{ display: "flex", gap: 26, marginBottom: 20 }}>
                <div style={{ width: 30, height: 30, flex: "none", background: C.blue, border: `3px solid ${C.ink}` }} />
                <div>
                  <div style={{ fontSize: 29, fontWeight: 700 }}>{n.t}</div>
                  <div style={{ fontSize: 22, color: C.ink2, marginTop: 3, lineHeight: 1.3 }}>{n.d}</div>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </Slide>
  );
}
