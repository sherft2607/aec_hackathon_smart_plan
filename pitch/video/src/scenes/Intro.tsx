// The 8-bit logo builds itself, holds, then settles into the deck's title slide.
import { AbsoluteFill, Freeze, Img, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame } from "remotion";

import { C, GROTESK } from "../theme";
import { Eyebrow, Headline, Reveal, useSceneFade, useSpring } from "../ui";

const BUILD = 96; // the 1.6 s clip at half speed

export function LogoBuild({ hold }: { hold: number }) {
  return (
    <AbsoluteFill style={{ background: "#ece8df" }}>
      <Sequence durationInFrames={BUILD}>
        <OffthreadVideo src={staticFile("intro.mp4")} playbackRate={0.5} muted style={{ width: "100%", height: "100%" }} />
      </Sequence>
      <Sequence from={BUILD} durationInFrames={hold}>
        <Freeze frame={BUILD - 1}>
          <OffthreadVideo src={staticFile("intro.mp4")} playbackRate={0.5} muted style={{ width: "100%", height: "100%" }} />
        </Freeze>
      </Sequence>
    </AbsoluteFill>
  );
}

export function Intro({ duration }: { duration: number }) {
  const frame = useCurrentFrame();
  const settle = 120;
  const title = interpolate(frame, [settle, settle + 18], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const fade = useSceneFade(duration, 1, 12);
  const logo = useSpring(settle, 20);
  return (
    <AbsoluteFill style={{ opacity: fade }}>
      <LogoBuild hold={duration - BUILD} />
      <AbsoluteFill
        style={{
          opacity: title,
          background: C.paper,
          backgroundImage: `linear-gradient(${C.paperLine} 1px, transparent 1px), linear-gradient(90deg, ${C.paperLine} 1px, transparent 1px)`,
          backgroundSize: "60px 60px",
          fontFamily: GROTESK,
          color: C.ink,
        }}
      >
        <Img
          src={staticFile("logo-8bit.png")}
          style={{ position: "absolute", right: 70, top: 120, width: 960, transform: `translate(${(1 - logo) * -380}px, ${(1 - logo) * 40}px) scale(${0.8 + 0.2 * logo})` }}
        />
        <div style={{ position: "absolute", left: 120, top: 250, width: 900 }}>
          <Eyebrow delay={settle + 6}>AECtech Hackathon · NYC</Eyebrow>
          <Headline
            delay={settle + 10}
            size={112}
            style={{ marginTop: 28 }}
            lines={[["Build", "on"], ["hindsight."], ["Design", "with"], [{ t: "foresight.", color: C.blue }]]}
          />
          <Reveal delay={settle + 40}>
            <p style={{ fontSize: 36, lineHeight: 1.35, color: C.ink2, marginTop: 34, maxWidth: 820 }}>
              Risk intelligence for every NYC site, so architects and engineers see the warnings before work starts.
            </p>
          </Reveal>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
}
