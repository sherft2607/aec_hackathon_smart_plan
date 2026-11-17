// The product demo: the Playwright take of the real app, full screen, cut into segments, sped up, and zoomed
// toward whatever the user is reading. Times are seconds in the source recording (public/demo/markers.json).
import { AbsoluteFill, Easing, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame } from "remotion";

import { C, FPS, GROTESK, H, PIXEL, W } from "../theme";
import { Eyebrow, Headline, Reveal, Slide } from "../ui";

type Key = { t: number; z: number; x: number; y: number };
type Segment = { from: number; to: number; speed: number; keys: Key[]; chip?: string };

const PANEL = { x: 1640, y: 470 };
const wide = (t: number): Key => ({ t, z: 1, x: W / 2, y: H / 2 });
const panel = (t: number, z = 1.45, y = PANEL.y): Key => ({ t, z, x: PANEL.x, y });

export const SEGMENTS: Segment[] = [
  { from: 1.0, to: 12.6, speed: 2.0, chip: "01 · Pick a site", keys: [wide(1), wide(2.6), { t: 3.6, z: 1.6, x: 480, y: 200 }, { t: 6.8, z: 1.6, x: 480, y: 200 }, wide(8.2), wide(12.6)] },
  { from: 12.6, to: 26.7, speed: 1.5, chip: "02 · Similar projects, and what went wrong", keys: [wide(12.6), panel(14.2, 1.45, 520), panel(21, 1.45, 620), panel(26.2, 1.45, 620), wide(26.7)] },
  { from: 26.7, to: 45.6, speed: 1.6, keys: [wide(26.7), wide(33.8), { t: 35, z: 1.35, x: 1020, y: 520 }, { t: 45.6, z: 1.35, x: 1020, y: 600 }] },
  { from: 50.0, to: 66.0, speed: 1.6, chip: "03 · This lot: early warnings", keys: [wide(50), panel(52, 1.45, 470), panel(56, 1.45, 600), panel(66, 1.45, 640)] },
  { from: 64.5, to: 94.3, speed: 1.8, chip: "04 · Start a project", keys: [panel(64.5, 1.45, 330), panel(70.5, 1.45, 330), wide(75.7), { t: 77.5, z: 1.4, x: 960, y: 330 }, { t: 84, z: 1.4, x: 960, y: 330 }, { t: 86, z: 1.25, x: 960, y: 760 }, { t: 92, z: 1.25, x: 960, y: 760 }, wide(94.3)] },
  { from: 94.3, to: 118.5, speed: 1.6, chip: "05 · One checklist for the whole team", keys: [wide(94.3), { t: 96, z: 1.35, x: 960, y: 380 }, { t: 102.9, z: 1.35, x: 960, y: 380 }, { t: 104, z: 1.4, x: 960, y: 600 }, { t: 108.5, z: 1.4, x: 960, y: 600 }, { t: 110.5, z: 1.45, x: 960, y: 640 }, { t: 118, z: 1.45, x: 960, y: 640 }, wide(118.5)] },
  { from: 119.5, to: 146.5, speed: 1.6, chip: "06 · Ask the chat", keys: [wide(119.5), { t: 121, z: 1.45, x: 960, y: 760 }, { t: 146.5, z: 1.45, x: 960, y: 720 }] },
];

const TITLE = 75;
const CARD = 60;
const clipFrames = (s: Segment) => Math.round(((s.to - s.from) * FPS) / s.speed);
const frames = (s: Segment) => clipFrames(s) + (s.chip ? CARD : 0);
export const DEMO_FRAMES = TITLE + SEGMENTS.reduce((n, s) => n + frames(s), 0);

function camera(keys: Key[], t: number) {
  const ease = Easing.inOut(Easing.cubic);
  const at = (k: keyof Key) => interpolate(t, keys.map((x) => x.t), keys.map((x) => x[k]), { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const z = at("z");
  const tx = Math.min(0, Math.max(W - W * z, W / 2 - at("x") * z));
  const ty = Math.min(0, Math.max(H - H * z, H / 2 - at("y") * z));
  return `translate(${tx}px, ${ty}px) scale(${z})`;
}

// A step title gets its own short card between clips, so it never covers the product.
function StepCard({ text }: { text: string }) {
  const frame = useCurrentFrame();
  const o = Math.min(
    interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" }),
    interpolate(frame, [CARD - 8, CARD], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
  );
  const [num, ...rest] = text.split(" · ");
  const title = rest.length ? rest.join(" · ") : num;
  return (
    <AbsoluteFill style={{ fontFamily: GROTESK, background: C.paper, backgroundImage: `linear-gradient(${C.paperLine} 2px, transparent 2px), linear-gradient(90deg, ${C.paperLine} 2px, transparent 2px)`, backgroundSize: "60px 60px" }}>
      <div style={{ position: "absolute", left: 120, top: 420, opacity: o, transform: `translateY(${(1 - o) * 20}px)` }}>
        {rest.length > 0 && <div style={{ fontFamily: PIXEL, fontSize: 26, letterSpacing: "0.16em", color: C.blue }}>STEP {num}</div>}
        <div style={{ fontSize: 96, fontWeight: 700, letterSpacing: "-0.03em", marginTop: 16, color: C.ink }}>{title}</div>
      </div>
    </AbsoluteFill>
  );
}

function Clip({ s, cutIn }: { s: Segment; cutIn: boolean }) {
  const frame = useCurrentFrame();
  const t = s.from + (frame / FPS) * s.speed;
  const flash = cutIn ? interpolate(frame, [0, 8], [1, 0], { extrapolateRight: "clamp" }) : 0;
  return (
    <AbsoluteFill style={{ background: "#fff", overflow: "hidden" }}>
      <div style={{ position: "absolute", width: W, height: H, transformOrigin: "0 0", transform: camera(s.keys, t) }}>
        <OffthreadVideo src={staticFile("demo/demo.mp4")} trimBefore={Math.round(s.from * FPS)} playbackRate={s.speed} muted style={{ width: W, height: H }} />
      </div>
      <AbsoluteFill style={{ background: "#fff", opacity: flash }} />
    </AbsoluteFill>
  );
}

function DemoTitle() {
  return (
    <Slide section="Product demo" duration={TITLE + 8}>
      <div style={{ position: "absolute", left: 120, top: 330 }}>
        <Eyebrow>Live product · recorded in the app</Eyebrow>
        <Headline delay={3} size={96} style={{ marginTop: 20 }} lines={[["861", "Park", "Avenue,", "Brooklyn"]]} />
        <Reveal delay={14}>
          <p style={{ fontSize: 38, color: C.ink2, marginTop: 26, maxWidth: 1300, lineHeight: 1.35 }}>
            An active new-building site with excavation, next to attached neighbors built 1910–1931.
          </p>
        </Reveal>
      </div>
    </Slide>
  );
}

export function Demo() {
  let at = TITLE;
  return (
    <AbsoluteFill style={{ background: "#fff" }}>
      {SEGMENTS.map((s, i) => {
        const from = at;
        at += frames(s);
        const card = s.chip ? CARD : 0;
        const cutIn = !card && i > 0 && Math.abs(SEGMENTS[i - 1].to - s.from) > 0.5;
        return (
          <Sequence key={s.from} from={from} durationInFrames={frames(s)} premountFor={30}>
            {s.chip && (
              <Sequence durationInFrames={CARD}>
                <StepCard text={s.chip} />
              </Sequence>
            )}
            <Sequence from={card} durationInFrames={clipFrames(s)} premountFor={30}>
              <Clip s={s} cutIn={cutIn} />
            </Sequence>
          </Sequence>
        );
      })}
      <Sequence durationInFrames={TITLE + 8}>
        <DemoTitle />
      </Sequence>
    </AbsoluteFill>
  );
}
