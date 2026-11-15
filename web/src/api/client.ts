// Every screen reads data through here. Each call tries the API, then the deploy's saved snapshot, then
// the matching fixture in contracts/fixtures/; stub and fixture answers come back with `sample: true` so
// the UI can label them as sample data. Only an API that is not there falls back: when the API answers
// with its own error, the call rejects with an ApiError, so a failed query is never shown as sample data.
import type {
  ActionItem,
  Case,
  ChatRequest,
  ChatResponse,
  EarlyWarning,
  JobType,
  LayerCatalogEntry,
  LayerFeatureCollection,
  PatternScore,
  Project,
  SearchResult,
  SimilarCases,
  SiteOutlook,
  SiteProfile,
  Stage,
  WarningRuleCheck,
  WorkType,
} from "../contracts";

import actionsFixture from "../../../contracts/fixtures/actions.json";
import casesFixture from "../../../contracts/fixtures/cases.json";
import chatFixture from "../../../contracts/fixtures/chat_response.json";
import layerCatalogFixture from "../../../contracts/fixtures/layer_catalog.json";
import layerFeaturesFixture from "../../../contracts/fixtures/layer_features.json";
import patternFixture from "../../../contracts/fixtures/pattern_score.json";
import projectFixture from "../../../contracts/fixtures/project.json";
import searchFixture from "../../../contracts/fixtures/search_results.json";
import similarFixture from "../../../contracts/fixtures/similar_cases.json";
import siteProfileFixture from "../../../contracts/fixtures/site_profile.json";
import warningChecksFixture from "../../../contracts/fixtures/warning_checks.json";
import warningsFixture from "../../../contracts/fixtures/warnings.json";

// `savedAt` is set when the answer came from the deploy's snapshot (tools/demo_snapshot.py): show its date.
export type Loaded<T> = { data: T; sample: boolean; savedAt?: string };

const FIXTURE_HEADER = "X-ForeSite-Fixture";
// VITE_API_BASE points a deployed web app at the deployed API; VITE_STATIC=1 skips the API entirely.
export const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");
export const STATIC = import.meta.env.VITE_STATIC === "1";
const SNAPSHOT = `${import.meta.env.BASE_URL}snapshot/`;

type Manifest = { saved_at: string; routes: Record<string, { sample: boolean }> };
let manifest: Promise<Manifest | null> | null = null;

// Same key as snapshot_key() in tools/demo_snapshot.py: '/api/search?q=2625 Bedford' -> 'search@q=2625-bedford'.
export function snapshotKey(path: string): string {
  const url = new URL(path, "http://x");
  const query = [...url.searchParams.entries()]
    .sort(([a, av], [b, bv]) => (a === b ? (av < bv ? -1 : 1) : a < b ? -1 : 1))
    .map(([k, v]) => `${k}=${v.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "")}`)
    .join("&");
  const route = decodeURIComponent(url.pathname).replace(/^\/api\//, "").replace(/^\/+|\/+$/g, "");
  return query ? `${route}@${query}` : route;
}

async function fromSnapshot<T>(path: string): Promise<Loaded<T> | null> {
  manifest ??= fetch(`${SNAPSHOT}manifest.json`)
    .then((r) => (r.ok ? (r.json() as Promise<Manifest>) : null))
    .catch(() => null);
  const saved = await manifest;
  const key = snapshotKey(path);
  const route = saved?.routes[key];
  if (!saved || !route) return null;
  try {
    const response = await fetch(`${SNAPSHOT}${key}.json`);
    if (!response.ok) return null;
    return { data: (await response.json()) as T, sample: route.sample, savedAt: saved.saved_at };
  } catch {
    return null;
  }
}

/** The API answered this call with an error (its status and its reason): show "couldn't load", never data. */
export class ApiError extends Error {
  constructor(readonly status: number, readonly detail: string, readonly path: string) {
    super(`Couldn't load (${status}): ${detail}`);
    this.name = "ApiError";
  }
}

// FastAPI sends its own errors as JSON. A non-JSON error is something in front of it, such as the dev
// server's proxy (an empty 502 while the API is not running) or a host's error page: the API is not there.
async function apiError(response: Response, path: string): Promise<ApiError | null> {
  if (!response.headers.get("Content-Type")?.includes("application/json")) return null;
  const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
  const detail = typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail ?? body);
  return new ApiError(response.status, detail, path);
}

async function request<T>(path: string, fallback: unknown, init?: RequestInit): Promise<Loaded<T>> {
  const read = !init?.method || init.method === "GET";
  if (!STATIC) {
    let failed: ApiError | null = null;
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        ...init,
        headers: { "Content-Type": "application/json", ...init?.headers },
      });
      if (response.ok) {
        return { data: (await response.json()) as T, sample: response.headers.get(FIXTURE_HEADER) === "true" };
      }
      failed = await apiError(response, path);
    } catch {
      // not reachable: fall through to the snapshot, then the fixture
    }
    if (failed) throw failed;
  }
  const saved = read ? await fromSnapshot<T>(path) : null;
  return saved ?? { data: fallback as T, sample: true };
}

const site = (bbl: string) => `/api/sites/${encodeURIComponent(bbl)}`;

export const api = {
  layers: () => request<LayerCatalogEntry[]>("/api/layers", layerCatalogFixture),
  layerFeatures: (layerId: string) =>
    request<LayerFeatureCollection>(`/api/layers/${encodeURIComponent(layerId)}`, layerFeaturesFixture),
  search: (q: string) => request<SearchResult[]>(`/api/search?q=${encodeURIComponent(q)}`, searchFixture),
  siteProfile: (bbl: string) => request<SiteProfile>(`${site(bbl)}/profile`, siteProfileFixture),
  similar: (bbl: string) => request<SimilarCases>(`${site(bbl)}/similar`, similarFixture),
  /** What could go wrong here, for every option. No fixture: offline it comes back empty and marked sample. */
  outlook: (bbl: string) => request<SiteOutlook>(`${site(bbl)}/outlook`, { bbl, lessons: [] }),
  warnings: (bbl: string, asOf?: string) =>
    request<EarlyWarning[]>(`${site(bbl)}/warnings${asOf ? `?as_of=${encodeURIComponent(asOf)}` : ""}`, warningsFixture),
  warningChecks: (bbl: string, asOf?: string) =>
    request<WarningRuleCheck[]>(`${site(bbl)}/warnings/checks${asOf ? `?as_of=${encodeURIComponent(asOf)}` : ""}`, warningChecksFixture),
  pattern: (bbl: string) => request<PatternScore>(`${site(bbl)}/pattern`, patternFixture),
  /** With the project screen's setup choices, the checklist follows the job type and scope picked there. */
  actions: (bbl: string, opts: { jobType?: JobType; workTypes?: WorkType[]; depthFt?: number; proposedStoreys?: number; stage?: Stage } = {}) => {
    const q = new URLSearchParams();
    if (opts.jobType) q.set("job_type", opts.jobType);
    if (opts.workTypes?.length) q.set("work_types", opts.workTypes.join(","));
    if (opts.depthFt != null) q.set("excavation_depth_ft", String(opts.depthFt));
    if (opts.proposedStoreys != null) q.set("proposed_storeys", String(opts.proposedStoreys));
    if (opts.stage) q.set("stage", opts.stage);
    const query = q.toString();
    return request<ActionItem[]>(`${site(bbl)}/actions${query ? `?${query}` : ""}`, actionsFixture);
  },
  cases: () => request<Case[]>("/api/cases", casesFixture),
  project: (id: string) => request<Project>(`/api/projects/${encodeURIComponent(id)}`, projectFixture),
  chat: (body: ChatRequest) =>
    request<ChatResponse>("/api/chat", chatFixture, { method: "POST", body: JSON.stringify(body) }),
};
