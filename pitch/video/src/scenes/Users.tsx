// Who 4site is for, and the moments in a project when it helps.
import { interpolate, useCurrentFrame } from "remotion";

import { C } from "../theme";
import { Eyebrow, HardCard, Headline, PixelLabel, Slide } from "../ui";

const STAGES = [
  { t: "Before acquisition", q: "Is this a site with a known history?" },
  { t: "Design", q: "What did similar sites run into?" },
  { t: "Before filing", q: "What should the drawings and SOE require?" },
  { t: "During construction", q: "What is happening on the job and next door?" },
];

export function Users({ duration }: { duration: number }) {
  const frame = useCurrentFrame();
  const track = interpolate(frame, [70, 220], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <Slide section="Who it's for" index={3} duration={duration}>
      <div style={{ position: "absolute", left: 120, top: 100 }}>
        <Eyebrow>Who it’s for</Eyebrow>
        <Headline delay={4} size={72} style={{ marginTop: 14 }} lines={[["For", "the", "people", "who", "sign", "the", "drawings"]]} />
      </div>
      <div style={{ position: "absolute", left: 120, top: 280, display: "flex", gap: 30, alignItems: "stretch" }}>
        {["Architects", "Structural engineers"].map((r, i) => (
          <HardCard key={r} delay={14 + i * 6} style={{ width: 430, background: C.blue, color: "#fff", borderColor: C.ink }}>
            <PixelLabel color="rgba(255,255,255,0.8)">Primary</PixelLabel>
            <div style={{ fontSize: 48, fontWeight: 700, marginTop: 12 }}>{r}</div>
          </HardCard>
        ))}
        {["Developers", "Contractors"].map((r, i) => (
          <HardCard key={r} delay={30 + i * 6} style={{ width: 330 }} shadow={6}>
            <PixelLabel>Also</PixelLabel>
            <div style={{ fontSize: 40, fontWeight: 700, marginTop: 14 }}>{r}</div>
          </HardCard>
        ))}
      </div>
      <div style={{ position: "absolute", left: 120, right: 120, top: 600 }}>
        <PixelLabel color={C.ink} size={20} style={{ opacity: interpolate(frame, [56, 70], [0, 1], { extrapolateRight: "clamp" }) }}>From the first look to the last pour</PixelLabel>
        <div style={{ position: "relative", height: 8, background: C.paperLine, marginTop: 34 }}>
          <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${track * 100}%`, background: C.ink }} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", marginTop: -22 }}>
          {STAGES.map((s, i) => {
            const on = interpolate(track, [i / 3 - 0.08, i / 3], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <div key={s.t} style={{ opacity: 0.25 + 0.75 * on }}>
                <div style={{ width: 36, height: 36, background: on > 0.5 ? C.blue : C.paper, border: `3px solid ${C.ink}`, transform: `scale(${0.8 + 0.3 * on})` }} />
                <div style={{ fontSize: 34, fontWeight: 700, marginTop: 22 }}>{s.t}</div>
                <div style={{ fontSize: 26, color: C.ink2, marginTop: 8, maxWidth: 360, lineHeight: 1.3 }}>{s.q}</div>
              </div>
            );
          })}
        </div>
      </div>
    </Slide>
  );
}
