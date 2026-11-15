// The site panel body: overview (top signals, then lot facts tucked into sections) and similar cases. The
// checklist lives on the project screen, drawn for the job the user describes. Loads its two sources
// independently, so each tab shows a skeleton until its own data lands.
import "./site_panel.css";

import { useEffect, useState, type ReactNode } from "react";

import { api, type Loaded } from "../../api/client";
import { copy } from "../../copy";
import type { EarlyWarning, SimilarCases as SimilarCasesData, SiteProfile, WarningRuleCheck } from "../../contracts";
import { Badge, formatDate, SkeletonCard, Tabs } from "../../design";
import { SiteWarnings } from "../early_warnings/SiteWarnings";
import { SimilarProjects } from "../lessons/SimilarProjects";
import type { StrandControls } from "../similar_cases/SimilarCases";
import { LotFacts, Neighbors, SourcesChecked, WorkAndGround } from "./LotFacts";
import { Signals } from "./Signals";

export type SiteTab = "similar" | "overview";

type Data = {
  profile?: Loaded<SiteProfile>;
  similar?: Loaded<SimilarCasesData>;
  warnings?: Loaded<EarlyWarning[]>;
  checks?: Loaded<WarningRuleCheck[]>;
};

export function useSiteData(bbl: string | null) {
  const [data, setData] = useState<Data>({});
  useEffect(() => {
    setData({});
    if (!bbl) return;
    let live = true;
    const put = <K extends keyof Data>(key: K) => (value: Data[K]) => live && setData((d) => ({ ...d, [key]: value }));
    api.siteProfile(bbl).then(put("profile"));
    api.similar(bbl).then(put("similar"));
    api.warnings(bbl).then(put("warnings"));
    api.warningChecks(bbl).then(put("checks"));
    return () => {
      live = false;
    };
  }, [bbl]);
  return data;
}

export function SitePanel({ bbl, data, tab, onTab, strands, onStart }: {
  bbl: string; data: Data; tab: SiteTab; onTab: (t: SiteTab) => void; strands?: StrandControls; onStart?: () => void;
}) {
  const { profile, similar, warnings, checks } = data;
  const sample = [profile, similar].some((x) => x?.sample);
  const count = (n?: number) => (n == null ? "" : ` ${n}`);

  return (
    <>
      <div className="fs-site__bar">
        <Tabs<SiteTab>
          label="Site sections"
          value={tab}
          onChange={onTab}
          options={[
            { value: "similar", label: <span className="fs-num">Similar projects{count(similar?.data.results.length)}</span> },
            { value: "overview", label: "This lot" },
          ]}
        />
        <div className="fs-site__meta">
          {profile?.data.as_of && <span className="fs-num">{copy.sitePanel.asOf} {formatDate(profile.data.as_of)}</span>}
          {sample && <Badge tone="sample">Sample data</Badge>}
        </div>
      </div>

      {tab === "overview" &&
        (profile ? (
          <>
            <Section title={copy.sitePanel.topSignals} help={copy.sitePanel.topSignalsHelp}>
              <Signals signals={profile.data.signals} datasets={profile.data.datasets} />
            </Section>
            <Section title="Early warnings" help="Record sequences on this site and its touching lots that are worth a look.">
              {warnings && checks ? <SiteWarnings warnings={warnings.data} checks={checks.data} /> : <SkeletonCard lines={2} />}
            </Section>
            <Section title="Work and ground" collapsible>
              <WorkAndGround profile={profile.data} />
            </Section>
            <Section title={`${copy.sitePanel.neighbors} (${profile.data.neighbors.length})`} collapsible>
              <Neighbors profile={profile.data} />
            </Section>
            <Section title={copy.sitePanel.lotFacts} collapsible>
              <LotFacts profile={profile.data} />
            </Section>
            <Section title="Sources checked" collapsible>
              <SourcesChecked profile={profile.data} />
              <p className="fs-quiet">{copy.sitePanel.housingNotScored}</p>
              <p className="fs-quiet">{copy.sitePanel.count311Apart}</p>
            </Section>
          </>
        ) : (
          <Loading />
        ))}

      {tab === "similar" && (similar
        ? <div className="fs-enter"><SimilarProjects bbl={bbl} results={similar.data.results} strands={strands} onStart={onStart} /></div>
        : <Loading />)}
    </>
  );
}

function Section({ title, help, children, collapsible }: { title: string; help?: string; children: ReactNode; collapsible?: boolean }) {
  if (!collapsible) {
    return (
      <section className="fs-site__section fs-enter">
        <h3 className="fs-label">{title}</h3>
        {help && <p className="fs-quiet">{help}</p>}
        {children}
      </section>
    );
  }
  return (
    <details className="fs-site__section fs-site__fold">
      <summary className="fs-label">{title}</summary>
      <div className="fs-site__foldbody">{children}</div>
    </details>
  );
}

function Loading() {
  return (
    <div className="fs-site__section" aria-busy="true">
      <SkeletonCard lines={2} />
      <SkeletonCard lines={2} />
      <SkeletonCard lines={1} />
    </div>
  );
}
