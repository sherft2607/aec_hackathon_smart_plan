// The logo builds again, then the closing line lands on the value: public warnings, turned into risk
// intelligence on the right building before work starts.
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";

import { C, GROTESK, PIXEL } from "../theme";
import { Headline, Reveal, useSceneFade, useSpring } from "../ui";
import { LogoBuild } from "./Intro";

export function Outro({ duration }: { duration: number }) {
  const frame = useCurrentFrame();
  const settle = 110;
  const page = interpolate(frame, [settle, settle + 16], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const logo = useSpring(settle, 20);
  const fade = useSceneFade(duration, 10, 24);
  return (
    <AbsoluteFill style={{ opacity: fade, background: "#000" }}>
      <LogoBuild hold={duration - 96} />
      <AbsoluteFill
        style={{
          opacity: page,
          background: C.paper,
          backgroundImage: `linear-gradient(${C.paperLine} 1px, transparent 1px), linear-gradient(90deg, ${C.paperLine} 1px, transparent 1px)`,
          backgroundSize: "60px 60px",
          fontFamily: GROTESK,
          color: C.ink,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Img src={staticFile("logo-8bit.png")} style={{ width: 460 + 200 * (1 - logo), marginTop: -40 }} />
        <div style={{ textAlign: "center", marginTop: 10 }}>
          <Headline
            delay={settle + 30}
            size={100}
            stagger={4}
            style={{ marginTop: 22 }}
            lines={[["4site", "turns", "warnings", "into"], [{ t: "risk", color: C.blue }, { t: "intelligence,", color: C.blue }], ["before", "work", "starts."]]}
          />
          <Reveal delay={settle + 90}>
            <div style={{ fontFamily: PIXEL, fontSize: 22, letterSpacing: "0.2em", color: C.ink2, marginTop: 40 }}>
              BUILD ON HINDSIGHT · DESIGN WITH FORESIGHT
            </div>
          </Reveal>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
}
