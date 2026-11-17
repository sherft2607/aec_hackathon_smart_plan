// Impact: what changes for a project team, and how many sites it applies to today.
import { C } from "../theme";
import { Counter, Eyebrow, HardCard, Headline, PixelLabel, Reveal, Slide } from "../ui";

const CARDS = [
  { t: "The neighbor’s risk shows up on your site", d: "Records are joined across the lot line, so a warning filed next door is no longer missed." },
  { t: "Hindsight becomes a checklist", d: "Similar past cases turn into action items by role, each with its code section and the proof it needs." },
  { t: "One picture for the whole team", d: "Architect, engineer, developer and contractor work from the same sourced evidence, at every stage." },
];

export function Impact({ duration }: { duration: number }) {
  return (
    <Slide section="Impact" index={9} duration={duration}>
      <div style={{ position: "absolute", left: 120, top: 90 }}>
        <Eyebrow>Impact</Eyebrow>
        <Headline delay={4} size={72} style={{ marginTop: 14 }} lines={[["Look", "before", "you", "dig."], [{ t: "Know", color: C.blue }, { t: "before", color: C.blue }, { t: "you", color: C.blue }, { t: "sign.", color: C.blue }]]} />
      </div>
      <div style={{ position: "absolute", left: 120, right: 120, top: 380, display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 36 }}>
        {CARDS.map((c, i) => (
          <HardCard key={c.t} delay={18 + i * 9} style={{ minHeight: 280 }}>
            <PixelLabel color={C.blue} size={22}>{String(i + 1).padStart(2, "0")}</PixelLabel>
            <div style={{ fontSize: 36, fontWeight: 700, marginTop: 14, lineHeight: 1.15 }}>{c.t}</div>
            <div style={{ fontSize: 25, color: C.ink2, marginTop: 14, lineHeight: 1.35 }}>{c.d}</div>
          </HardCard>
        ))}
      </div>
      <Reveal delay={70} style={{ position: "absolute", left: 120, top: 760, display: "flex", alignItems: "baseline", gap: 28 }}>
        <span style={{ fontSize: 110, fontWeight: 700, letterSpacing: "-0.04em", color: C.red }}>
          <Counter to={1187} delay={74} frames={50} />
        </span>
        <span style={{ fontSize: 34, maxWidth: 1100, lineHeight: 1.3 }}>
          active excavation, foundation and SOE permits sit next to attached pre-1940 buildings in NYC today.
          <PixelLabel size={15} style={{ marginTop: 10 }}>4site watchlist · DOB NOW + PLUTO · Nov 14, 2026</PixelLabel>
        </span>
      </Reveal>
    </Slide>
  );
}
