// The team, as on the deck's team slide, with each person's discipline drawn out to show the mix.
import { Img, interpolate, staticFile, useCurrentFrame } from "remotion";

import { C } from "../theme";
import { Eyebrow, Headline, PixelLabel, Slide, useSpring } from "../ui";

const D = {
  arch: { label: "Architecture", color: C.blue },
  struct: { label: "Structural", color: "#d9822b" },
  comp: { label: "Computational design", color: C.green },
  ai: { label: "Software & AI", color: "#8a5cf5" },
  dev: { label: "Development", color: C.red },
} as const;
type Key = keyof typeof D;

const PEOPLE: { id: string; name: string; role: string; detail: string; d: Key[] }[] = [
  { id: "camilo", name: "Camilo Reinales", role: "BIM Manager, Workshop/APD", detail: "Assoc. AIA · ex-SOM design technology", d: ["arch", "comp"] },
  { id: "ethnie", name: "Ethnie Xu", role: "Development, F&T Group", detail: "M.Arch + MBA, Yale", d: ["dev", "arch"] },
  { id: "hongyu", name: "Hongyu Wu", role: "Structural Engineer, TYLin", detail: "MS Structural Engineering, Stanford", d: ["struct"] },
  { id: "jacob", name: "Jacob Russo", role: "Growth Engineer, Nomic", detail: "Licensed architect (AIA) · ex-SOM", d: ["arch", "comp", "ai"] },
  { id: "jahleel", name: "Jahleel Murray", role: "Co-founder, D.A. BluePrint", detail: "NYC permitting · software engineer, Meta", d: ["ai"] },
  { id: "lise", name: "Lise Michel", role: "Co-founder, D.A. BluePrint", detail: "AI engineer · MS Industrial & Systems Eng.", d: ["ai"] },
  { id: "rishabh", name: "Rishabh Srinivasan", role: "University of Maryland", detail: "M.S. Information Systems & AI", d: ["ai"] },
  { id: "shandon", name: "Shandon Herft", role: "Comp. Designer, TT CORE studio", detail: "MS Computational Design, CMU · B.Arch", d: ["comp", "arch"] },
];

function Person({ p, i }: { p: (typeof PEOPLE)[number]; i: number }) {
  const enter = useSpring(18 + i * 5, 16);
  const frame = useCurrentFrame();
  const tags = interpolate(frame, [150 + i * 3, 170 + i * 3], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ width: 400, opacity: enter, transform: `translateY(${(1 - enter) * 40}px)` }}>
      <div style={{ width: 150, height: 150, borderRadius: "50%", border: `4px solid ${C.ink}`, overflow: "hidden", background: "#ddd" }}>
        <Img src={staticFile(`team/${p.id}.jpg`)} style={{ width: "100%", height: "100%", objectFit: "cover", filter: "grayscale(1) contrast(1.05)" }} />
      </div>
      <div style={{ fontSize: 31, fontWeight: 700, marginTop: 18, letterSpacing: "-0.02em" }}>{p.name}</div>
      <div style={{ fontSize: 21, color: C.ink, marginTop: 4 }}>{p.role}</div>
      <div style={{ fontSize: 19, color: C.ink2, marginTop: 3 }}>{p.detail}</div>
      <div style={{ display: "flex", gap: 6, marginTop: 10, opacity: tags, transform: `translateY(${(1 - tags) * 8}px)` }}>
        {p.d.map((k) => (
          <span key={k} style={{ width: 34, height: 10, background: D[k].color }} />
        ))}
      </div>
    </div>
  );
}

export function Team({ duration }: { duration: number }) {
  const frame = useCurrentFrame();
  const legend = interpolate(frame, [190, 215], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <Slide section="Team" index={1} duration={duration}>
      <div style={{ position: "absolute", left: 120, top: 90 }}>
        <Eyebrow>The team</Eyebrow>
        <Headline delay={4} size={72} style={{ marginTop: 14 }} lines={[["Architects,", "engineers", "&", "builders"]]} />
      </div>
      <div style={{ position: "absolute", left: 120, top: 270, display: "grid", gridTemplateColumns: "repeat(4, 420px)", rowGap: 34 }}>
        {PEOPLE.map((p, i) => (
          <Person key={p.id} p={p} i={i} />
        ))}
      </div>
      <div style={{ position: "absolute", left: 120, right: 120, bottom: 110, display: "flex", alignItems: "center", gap: 34, opacity: legend, transform: `translateY(${(1 - legend) * 16}px)` }}>
        <PixelLabel color={C.ink} size={20} style={{ whiteSpace: "nowrap" }}>8 people · 5 disciplines</PixelLabel>
        {Object.values(D).map((d) => (
          <span key={d.label} style={{ display: "inline-flex", alignItems: "center", gap: 10, fontSize: 22, color: C.ink2 }}>
            <span style={{ width: 26, height: 10, background: d.color }} />
            {d.label}
          </span>
        ))}
      </div>
    </Slide>
  );
}
