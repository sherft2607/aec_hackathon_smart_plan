// Early warnings inside the site panel: record sequences on the site and its touching lots that are worth
// a look, on the design system's cards. A rule that couldn't run fully says so, so "nothing found" is
// never mistaken for "checked and clear".
import type { EarlyWarning, WarningRuleCheck } from "../../contracts";
import { SEVERITY_LABELS } from "../../contracts";
import { Card, EmptyState, Explain, formatDate, HAZARD_LABELS, SeverityMark, SourceLabel } from "../../design";
import { evidence } from "./evidence";

export function SiteWarnings({ warnings, checks }: { warnings: EarlyWarning[]; checks: WarningRuleCheck[] }) {
  const byRule = new Map(checks.map((c) => [c.rule_id, c]));
  const partial = checks.filter((c) => c.status === "error").length;
  const sorted = [...warnings].sort((a, b) => b.severity - a.severity);

  return (
    <div className="fs-signals">
      {sorted.length === 0 ? (
        <EmptyState title="No warning sequences in the records checked">
          {checks.filter((c) => c.status === "ok").length} rules ran cleanly. That is not an all-clear: the records are
          public and incomplete.
        </EmptyState>
      ) : (
        sorted.map((w) => <WarningCard key={w.id} warning={w} check={byRule.get(w.rule_id)} />)
      )}
      <p className="fs-quiet">
        Prompts to look, not findings or predictions. {checks.length} rules checked
        {partial > 0 ? `; ${partial} couldn't be fully checked (open a card to see why).` : "."}
      </p>
    </div>
  );
}

function WarningCard({ warning, check }: { warning: EarlyWarning; check?: WarningRuleCheck }) {
  const first = check?.sources[0];
  const records = warning.evidence_record_ids.map(evidence);
  const shown = records.slice(0, 3);
  const job = warning.evidence_record_ids.find((id) => id.startsWith("dob_now_filings:"))?.split(":")[1]?.split("-")[0];
  return (
    <Card
      hazard={warning.hazard}
      title={
        <span className="fs-signal__title">
          <SeverityMark level={warning.severity} />
          {warning.title}
        </span>
      }
      meta={<SourceLabel name={first?.name ?? records[0]?.source} url={first?.url} date={first?.date ?? warning.first_seen} />}
    >
      <span className="fs-signal__tags">
        {HAZARD_LABELS[warning.hazard]} · {SEVERITY_LABELS[warning.severity]} · since {formatDate(warning.first_seen)}
        {job && <> · job <span className="fs-num">{job}</span></>}
      </span>
      <Explain>
        <p>{warning.explanation}</p>
        <p className="fs-num">
          Records: {shown.map((r) => r.label).join(", ")}
          {records.length > shown.length ? ` and ${records.length - shown.length} more` : ""}
        </p>
        {check && <p>{check.detail}</p>}
      </Explain>
    </Card>
  );
}
