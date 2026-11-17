// Shared pieces in the deck's style: paper slides with a grid, pixel labels, hard-shadow cards, motion helpers.
import type { CSSProperties, ReactNode } from "react";
import { AbsoluteFill, Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";

import { C, GROTESK, PIXEL } from "./theme";

export const TOTAL_SECTIONS = 11;

export function useSpring(delay = 0, damping = 18, durationInFrames?: number) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - delay, fps, config: { damping, mass: 0.7 }, durationInFrames });
}

export function useRamp(from: number, to: number, ease = Easing.inOut(Easing.cubic)) {
  const frame = useCurrentFrame();
  return interpolate(frame, [from, to], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
}

/** A whole slide fades in and out at its edges, so cuts between scenes are soft. */
export function useSceneFade(duration: number, inFrames = 10, outFrames = 10) {
  const frame = useCurrentFrame();
  return Math.min(
    interpolate(frame, [0, inFrames], [0, 1], { extrapolateRight: "clamp" }),
    outFrames > 0 ? interpolate(frame, [duration - outFrames, duration], [1, 0], { extrapolateLeft: "clamp" }) : 1,
  );
}

export function Slide({
  dark = false,
  section,
  index,
  children,
  duration,
  holdEnd = false,
}: {
  dark?: boolean;
  section: string;
  index?: number;
  children: ReactNode;
  duration: number;
  /** The video's last slide stays at full brightness to the final frame. */
  holdEnd?: boolean;
}) {
  const fade = useSceneFade(duration, 10, holdEnd ? 0 : 10);
  const line = dark ? C.nightLine : C.paperLine;
  return (
    <AbsoluteFill
      style={{
        background: dark ? C.night : C.paper,
        backgroundImage: `linear-gradient(${line} 1px, transparent 1px), linear-gradient(90deg, ${line} 1px, transparent 1px)`,
        backgroundSize: "60px 60px",
        color: dark ? C.nightInk : C.ink,
        fontFamily: GROTESK,
        opacity: fade,
      }}
    >
      {children}
      <div style={{ position: "absolute", left: 100, right: 100, bottom: 46, display: "flex", justifyContent: "space-between", fontFamily: PIXEL, fontSize: 17, letterSpacing: "0.18em", color: dark ? "rgba(241,239,233,0.55)" : C.ink2 }}>
        <span>4SITE // {section.toUpperCase()}</span>
        {index != null && <span>{String(index).padStart(2, "0")} / {String(TOTAL_SECTIONS).padStart(2, "0")}</span>}
      </div>
    </AbsoluteFill>
  );
}

export function Eyebrow({ children, color = C.blue, delay = 0, style }: { children: ReactNode; color?: string; delay?: number; style?: CSSProperties }) {
  const p = useSpring(delay);
  return (
    <div style={{ fontFamily: PIXEL, fontSize: 24, letterSpacing: "0.22em", color, textTransform: "uppercase", opacity: p, transform: `translateY(${(1 - p) * 12}px)`, ...style }}>
      {children}
    </div>
  );
}

export type Word = string | { t: string; color?: string };

/** A headline whose words rise in one after another. Lines are arrays of words. */
export function Headline({ lines, delay = 0, size = 88, stagger = 3, style }: { lines: Word[][]; delay?: number; size?: number; stagger?: number; style?: CSSProperties }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  let i = 0;
  return (
    <div style={{ fontSize: size, fontWeight: 700, lineHeight: 1.06, letterSpacing: "-0.035em", ...style }}>
      {lines.map((line, li) => (
        <div key={li} style={{ display: "block" }}>
          {line.map((w, wi) => {
            const word = typeof w === "string" ? { t: w } : w;
            const p = spring({ frame: frame - delay - i++ * stagger, fps, config: { damping: 20, mass: 0.6 } });
            return (
              <span key={wi} style={{ display: "inline-block", marginRight: "0.24em", color: word.color, opacity: p, transform: `translateY(${(1 - p) * 0.35}em)` }}>
                {word.t}
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
}

export function Reveal({ delay = 0, children, y = 24, x = 0, style }: { delay?: number; children: ReactNode; y?: number; x?: number; style?: CSSProperties }) {
  const p = useSpring(delay);
  return <div style={{ opacity: p, transform: `translate(${(1 - p) * x}px, ${(1 - p) * y}px)`, ...style }}>{children}</div>;
}

export function HardCard({ children, style, delay = 0, dark = false, shadow = 12 }: { children: ReactNode; style?: CSSProperties; delay?: number; dark?: boolean; shadow?: number }) {
  const p = useSpring(delay, 16);
  const ink = dark ? C.nightInk : C.ink;
  return (
    <div
      style={{
        border: `3px solid ${ink}`,
        background: dark ? "transparent" : C.card,
        boxShadow: dark ? "none" : `${shadow * p}px ${shadow * p}px 0 ${ink}`,
        padding: "28px 32px",
        opacity: p,
        transform: `translateY(${(1 - p) * 30}px)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

export function PixelLabel({ children, color = C.ink2, size = 18, style }: { children: ReactNode; color?: string; size?: number; style?: CSSProperties }) {
  return <div style={{ fontFamily: PIXEL, fontSize: size, letterSpacing: "0.16em", color, textTransform: "uppercase", ...style }}>{children}</div>;
}

export function Logo({ name, size = 56, style }: { name: string; size?: number; style?: CSSProperties }) {
  return <Img src={staticFile(`logos/${name}`)} style={{ width: size, height: size, objectFit: "contain", ...style }} />;
}

export function Counter({ to, delay = 0, frames = 40, style }: { to: number; delay?: number; frames?: number; style?: CSSProperties }) {
  const frame = useCurrentFrame();
  const t = interpolate(frame - delay, [0, frames], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  return <span style={{ fontVariantNumeric: "tabular-nums", ...style }}>{Math.round(to * t).toLocaleString("en-US")}</span>;
}

/** An arrow drawn from left to right as `progress` goes 0 to 1. */
export function DrawLine({ x1, y1, x2, y2, progress, color = C.ink, width = 3, dash }: { x1: number; y1: number; x2: number; y2: number; progress: number; color?: string; width?: number; dash?: string }) {
  const len = Math.hypot(x2 - x1, y2 - y1);
  return (
    <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth={width} strokeLinecap="round"
      strokeDasharray={dash ?? `${len} ${len}`} strokeDashoffset={dash ? 0 : len * (1 - progress)} opacity={dash ? progress : 1} />
  );
}
