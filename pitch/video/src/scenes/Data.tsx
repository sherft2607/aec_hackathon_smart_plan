// Every data source, grouped by what it tells you, with the counts pulled for the city layers.
import { Img, staticFile } from "remotion";

import { Counter, Eyebrow, HardCard, Headline, Logo, PixelLabel, Reveal, Slide } from "../ui";
import { C } from "../theme";

type Line = { n?: number; t: string };
const GROUPS: { title: string; logos: string[]; lines: Line[] }[] = [
  { title: "Site and buildings", logos: ["cityweft.svg", "openstreetmap.svg"], lines: [{ t: "NYC GeoSearch · PLUTO · MapPLUTO" }, { t: "Building footprints" }, { t: "Cityweft 3D: OpenStreetMap, Overture, USGS 3DEP" }] },
  { title: "Construction and enforcement", logos: [], lines: [{ t: "DOB NOW filings and permits" }, { n: 16581, t: "structural complaints (2024–)" }, { n: 1495, t: "construction incidents (2024–)" }, { t: "DOB, ECB and safety violations" }] },
  { title: "Façades and vacates", logos: [], lines: [{ n: 7137, t: "façades filed unsafe or SWARMP" }, { n: 4864, t: "fire vacate orders" }, { n: 348, t: "FDNY vacate orders" }] },
  { title: "Ground, water, weather", logos: [], lines: [{ n: 602, t: "FEMA flood-zone areas" }, { n: 486, t: "Sandy inundation areas" }, { n: 15645, t: "311 flooding reports (12 mo)" }, { t: "USGS bedrock · USDA soil · Open-Meteo" }] },
  { title: "Environmental", logos: [], lines: [{ n: 9389, t: "E-designations" }, { n: 1410, t: "NYS DEC remediation sites" }] },
  { title: "Knowledge", logos: ["building-code.svg", "revit.svg"], lines: [{ n: 42, t: "past NYC cases, 2007–2026, as publicly reported" }, { t: "NYC Building Code 2022 (BC 3304, 3309)" }, { t: "Revit structural model export" }] },
];

export function Data({ duration }: { duration: number }) {
  return (
    <Slide section="Data" index={7} duration={duration}>
      <div style={{ position: "absolute", left: 120, top: 80 }}>
        <Eyebrow>Data sources</Eyebrow>
        <Headline delay={4} size={60} style={{ marginTop: 14 }} lines={[["All", "public.", "All", "dated.", "All", { t: "linked", color: C.blue }, { t: "to", color: C.blue }, { t: "the", color: C.blue }, { t: "site.", color: C.blue }]]} />
      </div>
      <Reveal delay={10} style={{ position: "absolute", right: 120, top: 128 }}>
        <Img src={staticFile("logos/nycopendata.svg")} style={{ width: 380 }} />
      </Reveal>
      <div style={{ position: "absolute", left: 120, right: 120, top: 250, display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 30 }}>
        {GROUPS.map((g, i) => (
          <HardCard key={g.title} delay={14 + i * 7} shadow={8} style={{ minHeight: 300, padding: "22px 26px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              {g.logos.map((l) => <Logo key={l} name={l} size={38} />)}
              <div style={{ fontSize: 28, fontWeight: 700, marginLeft: 4 }}>{g.title}</div>
            </div>
            <div style={{ marginTop: 14 }}>
              {g.lines.map((l) => (
                <div key={l.t} style={{ display: "flex", gap: 12, alignItems: "baseline", fontSize: 23, lineHeight: 1.5 }}>
                  {l.n != null && (
                    <span style={{ fontWeight: 700, minWidth: 100, color: C.blue }}>
                      <Counter to={l.n} delay={24 + i * 7} frames={40} />
                    </span>
                  )}
                  <span style={{ color: l.n != null ? C.ink : C.ink2 }}>{l.t}</span>
                </div>
              ))}
            </div>
          </HardCard>
        ))}
      </div>
      <PixelLabel color={C.ink} size={17} style={{ position: "absolute", left: 120, top: 950 }}>
        NYC Open Data and city, state and federal sources · pulled Nov 14, 2026 · a failed query is shown as unknown, never as zero
      </PixelLabel>
    </Slide>
  );
}
