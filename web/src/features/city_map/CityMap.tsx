// The map home: a full-bleed dark city map with every layer from /api/layers (clustered, fading in by
// zoom), extruded buildings, click to pick a site, a cinematic fly-to, and the site
// with its touching lots highlighted, the shared party wall glowing, and similar cases arcing in from
// across the city. 3D buildings come from Cityweft (the blocks around a picked site) or, to compare,
// Google Photorealistic 3D Tiles (citywide, needs VITE_GOOGLE_MAPS_KEY); a switch on the map picks one.
import type { Layer } from "@deck.gl/core";
import { MapboxOverlay } from "@deck.gl/mapbox";
import type { Feature, FeatureCollection, Point } from "geojson";
import { type GeoJSONSource, Map as MapLibreMap, type MapGeoJSONFeature, Popup, setWorkerUrl } from "maplibre-gl";
// MapLibre looks for its worker next to its own module, which a production bundle moves; point it at the copied file.
import mapWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import { useCallback, useEffect, useRef, useState } from "react";

import "./city_map.css";

setWorkerUrl(mapWorkerUrl);

import { api } from "../../api/client";
import type { LayerFeature } from "../../contracts";
import { SEVERITY_LABELS } from "../../contracts";
import type { LayerState } from "../layer_panel/LayerPanel";
import {
  addAreaLayers, addBuildings, addPointLayers, addSiteLayers, applyMapPalette, areaLayerIds, basemapFor, type MapTheme,
  NYC_CENTER, pointLayerIds, sourceId,
} from "./map_style";
import { loadSiteLots, type Picked, siteAt } from "./site_lots";
import {
  addSelectionLayers, blinkSelection, clearSelection, loadSiteBuildings, setSiteBuildings, viewMode,
} from "./selection_blink";
import {
  ADJACENT_M, GOOGLE_KEY, googleTiles, KIND_COLORS, loadMeshLayers, loadSiteModel, type ModelScope, similarCaseLayers,
  similarCaseTooltip, type SiteModel, siteModelLayer,
} from "./story_layers";
import { boundsFor, fitPadding, resultsFor, visibleStrands } from "./strands";
import type { SimilarCase } from "../../contracts";
import { CameraControls } from "./CameraControls";

// The shell owns the picked site, the layer toggles and the search; the map draws them and reports clicks.
// Without `enabled`, every layer keeps its catalog default.
type Props = {
  site?: Picked | null;
  onPick?: (site: Picked) => void;
  enabled?: Set<string>;
  onSample?: () => void;
  /** The page theme: the basemap and the map's own colours follow it. */
  theme?: MapTheme;
  /** The similar case joined to the site by a strand, and framed with it. */
  focusCaseId?: string | null;
  /** Draw every similar case's strand, not only the focused one. */
  showAllStrands?: boolean;
  /** A case's dot on the map was clicked. */
  onFocusCase?: (caseId: string) => void;
};

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
// The longest a strand waits for the camera before it starts drawing anyway.
const STRAND_WAIT_MS = 2500;

/** "Why am I seeing this?": what the record is, its severity, source and date. Built as DOM, never HTML. */
function recordCard(p: Record<string, unknown>): HTMLElement {
  const el = document.createElement("div");
  el.className = "fs-popup";
  const title = el.appendChild(document.createElement("strong"));
  title.textContent = String(p.title ?? "Record");
  const summary = el.appendChild(document.createElement("p"));
  summary.textContent = String(p.summary ?? "");
  const meta = el.appendChild(document.createElement("p"));
  meta.className = "fs-popup-meta";
  const severity = SEVERITY_LABELS[Number(p.severity) as keyof typeof SEVERITY_LABELS] ?? "";
  meta.textContent = `${severity} · ${p.date ?? "undated"} · `;
  const link = meta.appendChild(document.createElement("a"));
  link.href = String(p.source_url ?? "#");
  link.target = "_blank";
  link.rel = "noreferrer";
  link.textContent = String(p.source_name ?? "source");
  return el;
}

type Source3d = "cityweft" | "google";
type CameraView = { center: [number, number]; zoom: number; pitch: number; bearing: number };
const CITY_VIEW: CameraView = { center: NYC_CENTER as [number, number], zoom: 10.4, pitch: 30, bearing: 0 };

/** Pick where the 3D buildings come from, to compare Cityweft with Google. Google needs its key. */
function Source3dSwitch({ value, onChange, note }: { value: Source3d; onChange: (s: Source3d) => void; note: string | null }) {
  const option = (id: Source3d, label: string, disabled = false, title?: string) => (
    <button
      type="button"
      disabled={disabled}
      title={title}
      aria-pressed={value === id}
      onClick={() => onChange(id)}
      className="fs-legend__opt disabled:cursor-not-allowed disabled:opacity-40"
    >
      {label}
    </button>
  );
  return (
    <div className="flex flex-col gap-1 text-[11px]">
      <div className="fs-legend fs-legend--row" role="group" aria-label="3D buildings from">
        <span className="fs-legend__muted">3D from</span>
        {option("cityweft", "Cityweft")}
        {option("google", "Google", !GOOGLE_KEY, GOOGLE_KEY ? undefined : "Set VITE_GOOGLE_MAPS_KEY to compare with Google 3D Tiles")}
      </div>
      {note && <span className="fs-cam__hint">{note}</span>}
    </div>
  );
}

const rgb = (c: readonly number[]) => `rgb(${c[0]}, ${c[1]}, ${c[2]})`;

// The focused case's building, raised in the accent blue (from the basemap's own footprint under it).
const CASE_BUILDING = "case-building";
function addCaseBuilding(map: MapLibreMap): void {
  map.addSource(CASE_BUILDING, { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  const firstLabel = map.getStyle().layers.find((l) => l.type === "symbol")?.id;
  map.addLayer(
    {
      id: CASE_BUILDING,
      type: "fill-extrusion",
      source: CASE_BUILDING,
      paint: {
        "fill-extrusion-color": "#4a6cf0",
        "fill-extrusion-height": ["*", ["coalesce", ["get", "render_height"], 12], 1.02],
        "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
        "fill-extrusion-opacity": 0.92,
      },
    },
    firstLabel,
  );
}
function setCaseBuilding(map: MapLibreMap, feature: Feature | null): void {
  (map.getSource(CASE_BUILDING) as GeoJSONSource | undefined)?.setData({
    type: "FeatureCollection",
    features: feature ? [feature] : [],
  });
}

/** What the Cityweft colours mean, and how much of the model to draw. */
function ModelLegend({ model, scope, onScope }: { model: SiteModel; scope: ModelScope; onScope: (s: ModelScope) => void }) {
  const option = (id: ModelScope, label: string, title: string) => (
    <button
      type="button"
      title={title}
      aria-pressed={scope === id}
      onClick={() => onScope(id)}
      className="fs-legend__opt"
    >
      {label} <span className="tabular-nums opacity-70">{model.counts[id]}</span>
    </button>
  );
  const key = (color: readonly number[], label: string) => (
    <span className="fs-legend__key">
      <span className="fs-legend__swatch" style={{ background: rgb(color) }} aria-hidden="true" />
      {label}
    </span>
  );
  return (
    <div className="fs-legend">
      <div className="fs-legend__keys">
        {key(KIND_COLORS.site, "Your site")}
        {key(KIND_COLORS.attached, "Attached")}
        {key(KIND_COLORS.other, "Other")}
      </div>
      <div className="fs-legend__opts" role="group" aria-label="Buildings shown">
        <span className="fs-legend__muted">Show</span>
        {option("adjacent", "Adjacent", `The site and buildings within ${ADJACENT_M} m of it`)}
        {option("area", "Wider area", "Every building Cityweft returned, about 500 m across")}
      </div>
    </div>
  );
}

export function CityMap({
  site: picked = null, onPick, enabled, onSample, theme = "light", focusCaseId = null, showAllStrands = false, onFocusCase,
}: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [ready, setReady] = useState(false);
  const [layers, setLayers] = useState<LayerState[]>([]);
  const [siteStatus, setSiteStatus] = useState<string | null>(null);
  const [sample, setSample] = useState(false);
  const [home, setHome] = useState<CameraView>(CITY_VIEW);
  const [source3d, setSource3d] = useState<Source3d>("cityweft");
  const [cityweftNote, setCityweftNote] = useState<string | null>(null);
  const [googleNote, setGoogleNote] = useState<string | null>(null);
  // The Cityweft model once it has risen; while rising it is drawn straight to deck.
  const [cityweft, setCityweft] = useState<{ model: SiteModel; meshLayers: Awaited<ReturnType<typeof loadMeshLayers>> } | null>(null);
  const [scope, setScope] = useState<ModelScope>("adjacent");
  const source3dRef = useRef<Source3d>("cityweft");
  source3dRef.current = source3d;
  const scopeRef = useRef<ModelScope>("adjacent");
  scopeRef.current = scope;
  const [googleLayer, setGoogleLayer] = useState<Layer | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const deckLayers = useRef<{ tiles: Layer[]; arcs: Layer[] }>({ tiles: [], arcs: [] });
  // Stops the current blink, if any. `selected` is true once the picked lot has drawn.
  const stopBlink = useRef<() => void>(() => {});
  const selected = useRef(false);
  // The similar cases for the picked site; which of them get a strand is decided by focus and the switch.
  // Kept with the site they were loaded for, so a newly picked site never uses the last site's cases.
  const [similarLoaded, setSimilar] = useState<{ bbl: string; results: SimilarCase[] } | null>(null);
  const similar = resultsFor(similarLoaded, picked?.bbl ?? null);
  const themeRef = useRef(theme);
  themeRef.current = theme;
  const onFocusRef = useRef(onFocusCase);
  onFocusRef.current = onFocusCase;
  // The basemap's own sources and layers, so a theme switch keeps everything else that was added.
  const baseStyle = useRef<{ sources: Set<string>; layers: Set<string> } | null>(null);
  const drawDeck = () => overlayRef.current?.setProps({ layers: [...deckLayers.current.tiles, ...deckLayers.current.arcs] });

  useEffect(() => {
    if (!container.current) return;
    const map = new MapLibreMap({ container: container.current, style: basemapFor(themeRef.current), ...CITY_VIEW, maxPitch: 75 });
    // Zoom, orbit, tilt and the 2D/3D switch live in CameraControls, bottom left.
    // Switching between 2D and 3D (the button, or tilting by hand) blinks the picked lot and building.
    let mode = viewMode(map.getPitch());
    map.on("pitchend", () => {
      const next = viewMode(map.getPitch());
      if (next === mode) return;
      mode = next;
      if (!selected.current) return;
      stopBlink.current();
      stopBlink.current = blinkSelection(map, reducedMotion());
    });
    // Not interleaved: with MapLibre 6 the shared-context mode drew nothing; its own canvas works.
    const overlay = new MapboxOverlay({ interleaved: false, layers: [], getTooltip: similarCaseTooltip as never });
    map.addControl(overlay);
    overlayRef.current = overlay;
    map.on("load", () => {
      const style = map.getStyle();
      baseStyle.current = { sources: new Set(Object.keys(style.sources)), layers: new Set(style.layers.map((l) => l.id)) };
      addBuildings(map);
      addCaseBuilding(map);
      addSiteLayers(map);
      addSelectionLayers(map);
      setReady(true);
    });
    mapRef.current = map;
    return () => {
      stopBlink.current();
      overlayRef.current = null;
      mapRef.current = null;
      setReady(false);
      map.remove();
    };
  }, []);

  // Load the catalog, then each layer's features into its own clustered source.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    let cancelled = false;
    api.layers().then(({ data, sample: s }) => {
      if (cancelled) return;
      setSample((was) => was || s);
      setLayers(data.map((entry) => ({ entry, on: entry.default_on, loaded: null, sample: s })));
      data.filter((e) => e.status !== "error").forEach((entry) => {
        api.layerFeatures(entry.layer_id).then(({ data: collection, sample: fs }) => {
          if (cancelled || !mapRef.current || map.getSource(sourceId(entry.layer_id))) return;
          setSample((was) => was || fs);
          // The offline fixture holds one layer's records; never show them under another layer's name.
          const features = collection.features.filter((f) => f.properties.layer_id === entry.layer_id);
          const points = features.filter((f) => f.geometry.type === "Point");
          const areas = features.filter((f) => f.geometry.type !== "Point");
          const asCollection = (fs2: LayerFeature[]) => ({ type: "FeatureCollection", features: fs2 }) as FeatureCollection;
          if (areas.length > 0) {
            map.addSource(sourceId(entry.layer_id), { type: "geojson", data: asCollection(areas) });
            addAreaLayers(map, entry.layer_id, entry.hazard, entry.default_on);
          } else {
            map.addSource(sourceId(entry.layer_id), {
              type: "geojson", data: asCollection(points), cluster: true, clusterRadius: 48, clusterMaxZoom: 14,
            });
            addPointLayers(map, entry.layer_id, entry.hazard, entry.default_on);
          }
          setLayers((ls) => ls.map((l) => (l.entry.layer_id === entry.layer_id ? { ...l, loaded: features.length, sample: fs } : l)));
        });
      });
    });
    return () => {
      cancelled = true;
    };
  }, [ready]);

  useEffect(() => {
    if (sample) onSample?.();
  }, [sample, onSample]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !enabled) return;
    for (const { entry } of layers) {
      for (const id of [...pointLayerIds(entry.layer_id), ...areaLayerIds(entry.layer_id)]) {
        // While a case is focused the map shows only the two places and their strand.
        const on = enabled.has(entry.layer_id) && !focusCaseId;
        if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
      }
    }
  }, [ready, layers, enabled, focusCaseId]);

  // Clicks: a cluster zooms in, a record explains itself, anywhere else picks the site under the cursor.
  const pickSite = useCallback((site: Picked) => onPick?.(site), [onPick]);
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const onClick = async (e: { point: [number, number] | { x: number; y: number }; lngLat: { lng: number; lat: number } }) => {
      // A click on a strand's pin belongs to deck (it focuses that case); never pick the lot under it too.
      const at = Array.isArray(e.point) ? { x: e.point[0], y: e.point[1] } : e.point;
      if (overlayRef.current?.pickObject({ ...at, radius: 8, layerIds: ["similar-case-origins", "strand-site"] })) return;
      const pointIds = layers.flatMap((l) => pointLayerIds(l.entry.layer_id)).filter((id) => map.getLayer(id));
      const hits: MapGeoJSONFeature[] = pointIds.length ? map.queryRenderedFeatures(e.point as never, { layers: pointIds }) : [];
      const hit = hits[0];
      if (hit?.properties.cluster_id != null) {
        const source = map.getSource(hit.source) as GeoJSONSource;
        const zoom = await source.getClusterExpansionZoom(hit.properties.cluster_id);
        map.easeTo({ center: (hit.geometry as Point).coordinates as [number, number], zoom, duration: reducedMotion() ? 0 : 400 });
        return;
      }
      if (hit) {
        new Popup({ closeButton: false, maxWidth: "280px" }).setLngLat(e.lngLat).setDOMContent(recordCard(hit.properties)).addTo(map);
        return;
      }
      const site = await siteAt(e.lngLat.lng, e.lngLat.lat);
      if (site) pickSite(site);
    };
    map.on("click", onClick);
    return () => {
      map.off("click", onClick);
    };
  }, [ready, layers, pickSite]);

  // Picking a site: fly in, then highlight it and its touching lots.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const empty: FeatureCollection = { type: "FeatureCollection", features: [] };
    (map.getSource("site-lots") as GeoJSONSource).setData(empty);
    (map.getSource("party-walls") as GeoJSONSource).setData(empty);
    stopBlink.current();
    selected.current = false;
    clearSelection(map);
    setSiteBuildings(map, empty);
    deckLayers.current.arcs = [];
    setSimilar(null);
    setCaseBuilding(map, null);
    setCityweft(null);
    drawDeck();
    setSiteStatus(null);
    setCityweftNote(null);
    if (!picked) return;
    let cancelled = false;
    // Far enough back to see the site with its surrounding blocks, not just the lot.
    const camera: CameraView = { center: [picked.lon, picked.lat], zoom: 16.4, pitch: 52, bearing: -28 };
    setHome(camera);
    if (reducedMotion()) map.jumpTo(camera);
    else map.flyTo({ ...camera, duration: 3200, curve: 1.6, essential: false });
    setSiteStatus("Loading the site and its touching lots…");
    setCityweftNote("Loading the Cityweft 3D model of the surrounding blocks…");
    let riseFrame = 0;
    // Cityweft's model of the blocks around the site; on failure the extruded buildings stay and the reason shows.
    // It waits for the camera to land, then the buildings rise out of the ground.
    const landsAt = performance.now() + (reducedMotion() ? 0 : 3200);
    const modelRequest = new AbortController();
    Promise.all([loadSiteModel(picked, modelRequest.signal), loadMeshLayers()])
      .then(([model, meshLayers]) => {
        if (cancelled) return;
        const sources = model.attributions.length ? ` (${model.attributions.join("; ")})` : "";
        setCityweftNote(`3D buildings from Cityweft${sources}`);
        const start = Math.max(performance.now(), landsAt);
        // Among towers, back off further so the camera isn't inside them: about a zoom level per 250 m over 80 m.
        const backOff = Math.min(1.4, Math.max(0, (model.tallestNearby - 80) / 250));
        if (backOff > 0.05) {
          setTimeout(() => {
            if (cancelled) return;
            const view = { ...camera, zoom: camera.zoom - backOff, pitch: camera.pitch - 4 * backOff };
            setHome(view);
            map.easeTo({ zoom: view.zoom, pitch: view.pitch, duration: reducedMotion() ? 0 : 1400 });
          }, Math.max(0, start - performance.now()));
        }
        const step = (now: number) => {
          if (cancelled) return;
          const t = reducedMotion() ? 1 : Math.min(1, Math.max(0, (now - start) / 1400));
          if (t < 1) {
            const layer = siteModelLayer(meshLayers, model, scopeRef.current, 1 - (1 - t) ** 3);
            // Drawn straight to deck while rising; the state only gets the finished layer.
            if (source3dRef.current === "cityweft" && now >= start) {
              deckLayers.current.tiles = [layer];
              drawDeck();
            }
            riseFrame = requestAnimationFrame(step);
          } else {
            setCityweft({ model, meshLayers });
          }
        };
        riseFrame = requestAnimationFrame(step);
      })
      .catch((error: Error & { status?: number }) => {
        if (cancelled || error.name === "AbortError") return;
        // 503 means this API has no Cityweft key: a setup choice, not a failure, so say it plainly.
        setCityweftNote(error.status === 503
          ? "Showing extruded buildings (Cityweft 3D isn't set up on this server)."
          : `Cityweft model unavailable: ${error.message}. Showing extruded buildings.`);
      });
    Promise.all([loadSiteLots(picked), loadSiteBuildings(picked.bbl)]).then(([{ lots, walls, profile, sample: s, note }, buildings]) => {
      if (cancelled) return;
      setSample((was) => was || s);
      (map.getSource("site-lots") as GeoJSONSource).setData(lots);
      (map.getSource("party-walls") as GeoJSONSource).setData(walls);
      setSiteBuildings(map, buildings);
      selected.current = true;
      // Blink once the camera has landed, so the eye is on the site when it happens.
      const blink = () => {
        if (cancelled) return;
        stopBlink.current();
        stopBlink.current = blinkSelection(map, reducedMotion());
      };
      if (map.isMoving()) map.once("moveend", blink);
      else blink();
      const touching = profile?.neighbors.length;
      setSiteStatus(note ?? `site and ${touching} touching lot${touching === 1 ? "" : "s"} highlighted`);
    });
    // The similar cases, kept for the strands; none are drawn until one is focused (or all are asked for).
    api.similar(picked.bbl).then(({ data, sample: s }) => {
      // The offline fixture is for one demo lot; never join its cases to a different site.
      if (cancelled || data.bbl !== picked.bbl) return;
      setSample((was) => was || s);
      setSimilar({ bbl: picked.bbl, results: data.results });
    });
    return () => {
      cancelled = true;
      modelRequest.abort();
      cancelAnimationFrame(riseFrame);
    };
  }, [ready, picked]);

  // Strands: the focused case (or all of them), drawn in from the case end. The line waits for the camera
  // to finish framing the two places (the effect below), then draws, so the whole stroke is seen.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !picked) return;
    const shown = visibleStrands(similar, focusCaseId, showAllStrands);
    let frame = 0;
    const asked = performance.now();
    let start: number | null = null;
    const step = (now: number) => {
      // Never wait longer than STRAND_WAIT_MS, so a user dragging the map can't hold the line back.
      if (start === null && (reducedMotion() || !map.isMoving() || now - asked > STRAND_WAIT_MS)) start = now;
      const t = start === null ? 0 : reducedMotion() ? 1 : Math.min(1, (now - start) / 1100);
      deckLayers.current.arcs = similarCaseLayers(picked, shown, 1 - (1 - t) ** 3, focusCaseId, (id) => onFocusRef.current?.(id));
      drawDeck();
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [ready, picked, similarLoaded, focusCaseId, showAllStrands]);

  // Focusing a case pulls the camera out to frame the site and that case, then highlights the case's building.
  // Letting go of the case flies back to the site's own view.
  const homeRef = useRef(home);
  homeRef.current = home;
  const framedCase = useRef<string | null>(null);
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    setCaseBuilding(map, null);
    const focused = similar.find((r) => r.case_id === focusCaseId);
    if (!picked || !focused) {
      if (picked && framedCase.current && !focusCaseId) {
        map.flyTo({ ...homeRef.current, duration: reducedMotion() ? 0 : 1800, essential: false });
      }
      framedCase.current = null;
      return;
    }
    framedCase.current = focused.case_id;
    const bounds = boundsFor(picked, focused.case);
    if (!bounds) return;
    let live = true;
    const highlight = () => {
      if (!live) return;
      const point = map.project([focused.case.lon, focused.case.lat]);
      const hit = map.getLayer("buildings-3d") ? map.queryRenderedFeatures(point, { layers: ["buildings-3d"] })[0] : undefined;
      setCaseBuilding(map, hit ? { type: "Feature", geometry: hit.geometry, properties: hit.properties ?? {} } : null);
    };
    // Listen first: with no animation the move ends inside fitBounds. "idle" waits for the new tiles to draw.
    map.once("idle", highlight);
    const { clientWidth, clientHeight } = map.getContainer();
    map.fitBounds(bounds, {
      padding: fitPadding(clientWidth, clientHeight),
      pitch: 45,
      bearing: map.getBearing(),
      maxZoom: 17,
      duration: reducedMotion() ? 0 : 1600,
    });
    return () => {
      live = false;
      map.off("idle", highlight);
    };
  }, [ready, picked, similarLoaded, focusCaseId]);

  // The basemap follows the theme. The swap keeps every source and layer added on top of the basemap.
  const appliedTheme = useRef<MapTheme | null>(null);
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    if (appliedTheme.current === null) {
      // The map was made with this theme's basemap; repaint in case layers were added before <html> had it.
      appliedTheme.current = theme;
      applyMapPalette(map, theme, layers.map((l) => l.entry.layer_id));
      return;
    }
    if (appliedTheme.current === theme) return;
    appliedTheme.current = theme;
    map.setStyle(basemapFor(theme), {
      transformStyle: (previous, next) => {
        const base = baseStyle.current;
        if (!previous || !base) return next;
        baseStyle.current = { sources: new Set(Object.keys(next.sources)), layers: new Set(next.layers.map((l) => l.id)) };
        const keptSources = Object.fromEntries(Object.entries(previous.sources).filter(([id]) => !base.sources.has(id)));
        // Custom layers that sat under the old labels go under the new ones, in their order; the rest on top.
        const oldFirstLabel = previous.layers.findIndex((l) => l.type === "symbol");
        const isUnder = (i: number) => oldFirstLabel >= 0 && i < oldFirstLabel;
        const under = previous.layers.filter((l, i) => !base.layers.has(l.id) && isUnder(i));
        const over = previous.layers.filter((l, i) => !base.layers.has(l.id) && !isUnder(i));
        const firstLabel = next.layers.findIndex((l) => l.type === "symbol");
        const at = firstLabel < 0 ? next.layers.length : firstLabel;
        return {
          ...next,
          sources: { ...next.sources, ...keptSources },
          layers: [...next.layers.slice(0, at), ...under, ...next.layers.slice(at), ...over],
        };
      },
    });
    map.once("style.load", () => applyMapPalette(map, theme, layers.map((l) => l.entry.layer_id)));
  }, [ready, theme, layers]);

  // Google tiles load the first time Google is picked, then stay ready for switching back and forth.
  useEffect(() => {
    if (source3d !== "google" || googleLayer || !GOOGLE_KEY) return;
    setGoogleNote("Loading Google 3D tiles…");
    googleTiles(GOOGLE_KEY, (c) => setGoogleNote(c ? `Google 3D tiles: ${c}` : "Google 3D tiles"))
      .then(setGoogleLayer)
      .catch(() => setGoogleNote("Google 3D tiles couldn't load; showing extruded buildings."));
  }, [source3d, googleLayer]);

  // Show the picked source's buildings. Google replaces the extrusions citywide; Cityweft sits on top of them.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const layer = source3d === "google" ? googleLayer : cityweft && siteModelLayer(cityweft.meshLayers, cityweft.model, scope);
    deckLayers.current.tiles = layer ? [layer] : [];
    if (map.getLayer("buildings-3d")) {
      map.setLayoutProperty("buildings-3d", "visibility", source3d === "google" && googleLayer ? "none" : "visible");
    }
    drawDeck();
  }, [ready, source3d, googleLayer, cityweft, scope]);

  // maplibre-gl.css sets the map element to position: relative, so it sizes to this wrapper instead.
  return (
    <div className="absolute inset-0">
      <div ref={container} className="h-full w-full" />
      {picked && siteStatus && (
        <div className="fs-hint" role="status">{siteStatus}</div>
      )}
      <div className="absolute bottom-20 left-4 flex max-w-sm flex-col gap-1.5">
        <CameraControls map={ready ? mapRef.current : null} site={picked ? [picked.lon, picked.lat] : null} home={home} />
        {source3d === "cityweft" && cityweft && <ModelLegend model={cityweft.model} scope={scope} onScope={setScope} />}
        <Source3dSwitch value={source3d} onChange={setSource3d} note={source3d === "google" ? googleNote : cityweftNote} />
      </div>
    </div>
  );
}
