// The tech stack as layers that build up from the data, with Cityweft called out.
import { interpolate, useCurrentFrame } from "remotion";

import { C } from "../theme";
import { Eyebrow, Headline, Logo, PixelLabel, Slide } from "../ui";

const LAYERS: { name: string; items: { logo: string; t: string }[] }[] = [
  { name: "Interface", items: [{ logo: "react.svg", t: "React 19" }, { logo: "typescript.svg", t: "TypeScript" }, { logo: "vite.svg", t: "Vite" }, { logo: "tailwind.svg", t: "Tailwind" }, { logo: "maplibre.svg", t: "MapLibre" }, { logo: "deckgl.png", t: "deck.gl" }, { logo: "vercel.svg", t: "Vercel" }] },
  { name: "Intelligence", items: [{ logo: "claude.svg", t: "Claude" }, { logo: "anthropic.svg", t: "Anthropic API" }] },
  { name: "Engine", items: [{ logo: "python.svg", t: "Python" }, { logo: "fastapi.svg", t: "FastAPI" }, { logo: "sqlite.svg", t: "SQLite" }] },
  { name: "Data", items: [{ logo: "nycopendata.svg", t: "NYC Open Data" }, { logo: "openstreetmap.svg", t: "OpenStreetMap" }, { logo: "revit.svg", t: "Revit" }] },
];

export function Stack({ duration }: { duration: number }) {
  const frame = useCurrentFrame();
  const cw = interpolate(frame, [70, 90], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <Slide section="Tech stack" index={8} duration={duration}>
      <div style={{ position: "absolute", left: 120, top: 80 }}>
        <Eyebrow>Tech stack</Eyebrow>
        <Headline delay={4} size={60} style={{ marginTop: 14 }} lines={[["Open", "data,", "open", "tools,", { t: "one", color: C.blue }, { t: "map", color: C.blue }]]} />
      </div>
      <div style={{ position: "absolute", left: 120, top: 250, width: 1080 }}>
        {LAYERS.map((l, i) => {
          const order = LAYERS.length - 1 - i;
          const p = interpolate(frame, [10 + order * 12, 26 + order * 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return (
            <div key={l.name} style={{ display: "flex", alignItems: "center", height: 150, marginBottom: 18, border: `3px solid ${C.ink}`, background: i === 1 ? "#e6ebff" : C.card, boxShadow: `${8 * p}px ${8 * p}px 0 ${C.ink}`, opacity: p, transform: `translateY(${(1 - p) * 60}px)` }}>
              <PixelLabel color={C.ink} size={19} style={{ width: 230, paddingLeft: 28 }}>{l.name}</PixelLabel>
              <div style={{ display: "flex", gap: 18 }}>
                {l.items.map((it) => (
                  <div key={it.t} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10, width: it.logo === "nycopendata.svg" ? 230 : 100 }}>
                    <Logo name={it.logo} size={58} style={it.logo === "nycopendata.svg" ? { width: 220 } : undefined} />
                    <div style={{ fontSize: 18, color: C.ink2, textAlign: "center" }}>{it.t}</div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", left: 1280, top: 250, width: 520, height: 654, border: `3px solid ${C.ink}`, background: "#054B4D", color: "#fff", boxShadow: `${12 * cw}px ${12 * cw}px 0 ${C.ink}`, opacity: cw, transform: `translateX(${(1 - cw) * 60}px)`, padding: 40, boxSizing: "border-box", display: "flex", flexDirection: "column" }}>
        <Logo name="cityweft.svg" size={150} />
        <div style={{ fontSize: 56, fontWeight: 700, marginTop: 30, letterSpacing: "-0.03em" }}>Cityweft</div>
        <div style={{ fontSize: 28, lineHeight: 1.35, marginTop: 14, color: "rgba(255,255,255,0.85)" }}>
          The 3D city: every building around the site, from OpenStreetMap, Overture, Meta & WRI canopy heights and USGS 3DEP elevation.
        </div>
        <PixelLabel color="rgba(255,255,255,0.7)" size={17} style={{ marginTop: "auto" }}>3D buildings · terrain · context</PixelLabel>
      </div>
    </Slide>
  );
}
