// Every user-facing string in ForeSite. Components import from here instead of writing their own words,
// so the tone stays one voice: calm, factual, no blame, no "would have prevented", never a verdict.
// Type-only imports, so tests/test_copy.py can load this file with Node and check the wording.
import type { ActionItem, Case, ChatResponse, Hazard, Severity, Stage } from "../contracts";

type Discipline = ActionItem["discipline"];
type ItemStatus = ActionItem["status"];
type CauseStatus = Case["cause_status"];
type AnswerKind = ChatResponse["answer_parts"][number]["kind"];
type Role = "architect" | "structural_engineer" | "developer" | "contractor";
type JobType = "new_building" | "alteration" | "demolition";
type QueryStatus = "ok" | "error" | "capped";

export const copy = {
  app: {
    name: "4site",
    tagline: "See what the public record says about a site and its neighbors, before work starts.",
    sampleData: "Sample data",
    sampleDataHint: "The live service is unavailable, so this screen shows saved sample records.",
  },

  // Always visible on every screen (the forensic advisor: "checking these boxes doesn't mean you're good").
  limitations: {
    title: "What 4site doesn't know",
    short: "Public records and reported cases only. Not exhaustive, and not engineering advice.",
    points: [
      "It shows what public records and reported cases say. It does not inspect buildings or read drawings it was not given.",
      "Lists here are not exhaustive. A clear list does not mean a site is free of risk.",
      "It is not a DOB determination, a code review, or engineering advice. The licensed professionals on the project decide.",
      "Records can be late, incomplete or wrong at the source. Every item links to where it came from.",
      "Similar cases share features with this site. They do not say what will happen here.",
    ],
    notExhaustive: "Not exhaustive",
  },

  // Where each piece of information comes from: part of the visual language, not a footnote.
  sourceLabels: {
    public_record: "Public record",
    case: "Reported case",
    warning: "Early warning",
    action: "Action item",
    ai_suggestion: "AI suggestion",
    web: "Web source",
    user_input: "Added by your team",
    not_found: "None found",
    unknown: "Couldn't load",
    notice: "Note",
  } satisfies Record<AnswerKind, string>,

  hazards: {
    structural: "Structural",
    geotech: "Soil and foundations",
    fire: "Fire",
    flood: "Flooding",
    contamination: "Contamination",
    facade: "Facade",
    weather: "Weather",
    construction_safety: "Construction safety",
  } satisfies Record<Hazard, string>,

  severity: {
    0: "Signal",
    1: "Enforcement",
    2: "Incident",
    3: "Catastrophic",
  } satisfies Record<Severity, string>,

  severityHelp: {
    0: "A complaint someone filed. Nobody has confirmed it yet.",
    1: "An official action: a violation, a stop-work order or a vacate order.",
    2: "Someone was hurt, or part of a structure failed.",
    3: "A death, or a full collapse.",
  } satisfies Record<Severity, string>,

  stages: {
    pre_acquisition: "Before buying",
    design: "Design",
    pre_filing: "Before filing",
    construction: "Construction",
  } satisfies Record<Stage, string>,

  stageHelp: {
    pre_acquisition: "Is this lot worth buying, and what would building here involve?",
    design: "What should shape the design: neighbors, soil, flood and past cases.",
    pre_filing: "What should be settled before the job is filed with DOB.",
    construction: "What to watch while work is under way, especially before digging.",
  } satisfies Record<Stage, string>,

  roles: {
    architect: "Architect",
    structural_engineer: "Structural engineer",
    developer: "Developer",
    contractor: "Contractor",
  } satisfies Record<Role, string>,

  disciplines: {
    architect: "Architect",
    structural: "Structural engineer",
    geotech: "Geotechnical engineer",
    contractor: "Contractor",
  } satisfies Record<Discipline, string>,

  jobTypes: {
    new_building: "New building",
    alteration: "Alteration",
    demolition: "Demolition",
  } satisfies Record<JobType, string>,

  itemStatus: {
    open: "Open",
    in_progress: "In progress",
    done: "Done",
    not_applicable: "Doesn't apply",
  } satisfies Record<ItemStatus, string>,

  causeStatus: {
    reported: "As publicly reported",
    under_investigation: "Under investigation",
    unknown: "Cause not reported",
  } satisfies Record<CauseStatus, string>,

  // A failed query is never zero; a capped one is a floor.
  queryStatus: {
    ok: "Loaded",
    error: "Couldn't load",
    capped: "At least",
  } satisfies Record<QueryStatus, string>,

  map: {
    searchPlaceholder: "Search an NYC address, or click a building",
    searchNoResults: "No address matched. Try the house number and street, then the borough.",
    flyingTo: "Going to the site…",
    siteMatched: "Matched",
    neighborsHighlighted: "The site and its touching lots are outlined.",
    neighborsMissing: "Touching lots couldn't load for this site.",
    partyWall: "Shared wall with an attached neighbor",
    clusterHint: "Zoom in to see each record.",
  },

  layers: {
    title: "Layers",
    hide: "Hide",
    updated: "Updated",
    updatedUnknown: "Update date unknown",
    noSampleRecords: "No sample records",
    loading: "Loading…",
    defaultOffHint: "Off by default. Turn it on when it matters for this site.",
  },

  sitePanel: {
    topSignals: "What stands out",
    topSignalsHelp: "The three records that matter most here, life-safety items first.",
    lotFacts: "Lot facts",
    neighbors: "Touching lots",
    attached: "Attached",
    detached: "Not attached",
    yearUnknown: "Year built unknown",
    housingNotScored: "Housing violations are shown but never counted as structural risk.",
    count311Apart: "311 requests are counted apart from DOB complaints, because the same report can appear in both.",
    asOf: "Records dated before",
    noSignals: "No records in the structural, safety or flood categories were found for this site.",
  },

  similarCases: {
    title: "Similar cases across the city",
    help: "Past NYC cases that share features with this site. They show where projects like this one ran into trouble, not what will happen here.",
    matchesOn: "Matches on",
    differsOn: "Differs on",
    score: "Similarity",
    scoreHelp: "How many of this site's features the case shares. It is not a likelihood.",
    filters: { hazard: "Hazard", severity: "Severity", date: "Date" },
    empty: "No similar cases match these filters.",
  },

  warnings: {
    title: "Early warnings",
    help: "Sequences in the dated record that came before incidents elsewhere. A warning is a reason to ask, not a finding.",
    firstSeen: "First seen",
    evidence: "Records behind it",
    empty: "No warning sequences found in the records dated before this day.",
  },

  pattern: {
    title: "Compared with similar sites",
    help: "Where this site's record pattern sits among sites with a similar profile. It is not a forecast for this building.",
    percentile: "Higher than",
    percentileSuffix: "of similar sites",
    comparedWith: "Compared with",
    topFactors: "What moves it most",
    calibration: "How to read this",
  },

  actions: {
    title: "Actions by discipline",
    help: "Code duties and hazard checks that apply to this kind of work here. Not exhaustive.",
    owner: "Owner",
    proofNeeded: "Proof needed",
    codeRef: "Code",
    lifeSafety: "Life safety",
    proofNote: "Proof comes from the team. 4site never treats a public record as proof.",
    empty: "No actions for this stage yet.",
  },

  chat: {
    title: "Ask about this site",
    placeholder: "Ask about this site, for example: what happened next door?",
    pin: "Pin to project",
    pinned: "Pinned",
    offline: "The assistant is offline. These are saved answers for the sample site.",
    sourcesHelp: "Each part of an answer says where it came from. Click a source to see it on the map.",
  },

  project: {
    title: "Project",
    members: "Team",
    items: "Assigned items",
    notes: "Notes",
    pins: "Pinned",
    addNote: "Add a note",
    sharedHelp: "Everyone on the project sees the same site, items and notes.",
  },

  states: {
    loading: "Loading…",
    couldntLoad: "Couldn't load. This is a loading problem, not a sign that nothing is there.",
    retry: "Try again",
    offline: "Offline: showing saved sample data.",
  },
} as const;

/** A count that respects the query's status: an error is never a number, a capped count is a floor. */
export function countText(status: QueryStatus, count: number | null): string {
  if (status === "error") return copy.queryStatus.error;
  if (count == null) return copy.states.loading;
  const n = count.toLocaleString("en-US");
  return status === "capped" ? `${copy.queryStatus.capped} ${n}` : n;
}

/** "Records dated before 2026-06-01": as-of always means dated before that day. */
export function asOfText(date: string): string {
  return `${copy.sitePanel.asOf} ${date}`;
}

/** The cause line for a past case: only as publicly reported, or under investigation. */
export function causeText(status: CauseStatus, cause: string | null): string {
  if (status === "reported" && cause) return `${copy.causeStatus.reported}: ${cause}`;
  return copy.causeStatus[status === "reported" ? "unknown" : status];
}
