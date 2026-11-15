// The app shell: a full-bleed map with floating panels over it. The user never leaves the map.
//   top left      brand, search (/ or Cmd/Ctrl-K), panel buttons
//   left          layers (the layer panel, PR 5, fills it)
//   right         the picked site (PR 10)
//   bottom centre the chat (PR 9): its question box is always there, the conversation opens above it
//   bottom left   "What 4site doesn't know", always visible
// Each panel can be moved, resized, minimised and maximised (MapWindow.tsx); these are where they start.
// What is open lives in the URL (url_state.ts), so every view can be shared.
import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../api/client";
import type { LayerCatalogEntry, SearchResult } from "../contracts";
import { copy } from "../copy";
import logo from "../design/brand/4site-logo.png";
import { Button, Kbd, KeyboardIcon, LayersIcon, MoonIcon, SearchIcon, SunIcon } from "../design";
import { CityMap } from "../features/city_map/CityMap";
import type { Picked } from "../features/city_map/site_lots";
import { LimitationsPanel } from "../features/limitations/LimitationsPanel";
import { useProjectIdInUrl } from "../features/project/project_url";
import { useProject } from "../features/project/useProject";
import { ProjectScreen } from "../features/project_screen/ProjectScreen";
import { CommandBar, titleCase, type Command } from "./CommandBar";
import { Intro } from "./Intro";
import { useTheme } from "./preferences";
import { ShortcutsHelp } from "./ShortcutsHelp";
import { keyLabel, useShortcuts, type Shortcut } from "./shortcuts";
import { ChatSlot, DataStatus, LayerSlot, SiteSlot } from "./slots";
import { useViewState } from "./url_state";
import { layersForWork, shouldApply } from "./work_layers";
// After the design system's CSS (imported through ../design), so layout rules win over component defaults.
import "./shell.css";

export function App() {
  const [view, setView] = useViewState();
  const [theme, toggleTheme] = useTheme();
  const [commandOpen, setCommandOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  const [layers, setLayers] = useState<LayerCatalogEntry[] | null>(null);
  const [enabled, setEnabled] = useState<Set<string>>(new Set());
  const [site, setSite] = useState<SearchResult | null>(null);
  const [sample, setSample] = useState(false);
  const markSample = useCallback(() => setSample(true), []);
  // The shell materialises once the opening logo has played (or straight away when it is skipped).
  const [entered, setEntered] = useState(false);
  const enter = useCallback(() => setEntered(true), []);
  // One strand at a time: the focused similar case, or every strand when the switch is on.
  const [focusCase, setFocusCase] = useState<string | null>(null);
  const [allStrands, setAllStrands] = useState(false);
  const toggleFocus = useCallback((caseId: string) => setFocusCase((current) => (current === caseId ? null : caseId)), []);
  useEffect(() => setFocusCase(null), [view.site]);
  // The project screen's project: polled only while the screen is open (the chat dock has its own).
  const [projectId, openProject] = useProjectIdInUrl();
  const workspace = useProject(view.screen === "project" ? projectId : null);
  // A project belongs to the site it was made for: continuing from another site starts a new one.
  const openSiteBbl = workspace.state.status === "ok" ? workspace.state.project.site_bbl : null;
  // Back on the map from a project, its work type switches on the layers that matter for it, once: a
  // layer toggled by hand afterwards stays as it was set.
  const projectJob = useRef<string | null>(null);
  const appliedJob = useRef<string | null>(null);
  if (workspace.state.status === "ok" && workspace.state.project.job_type) {
    projectJob.current = `${workspace.state.project.id}:${workspace.state.project.job_type}`;
  }
  useEffect(() => {
    const key = projectJob.current;
    if (view.screen !== "map" || !layers || !shouldApply(appliedJob.current, key)) return;
    appliedJob.current = key;
    const job = key!.split(":")[1] as Parameters<typeof layersForWork>[0];
    setEnabled(layersForWork(job, layers.filter((l) => l.status !== "error").map((l) => l.layer_id)));
  }, [view.screen, layers]);

  // So does a link to a project the store doesn't have (another server, or a store file that was reset).
  const projectMissing = workspace.state.status === "not_found";
  useEffect(() => {
    if (view.screen !== "project" || !view.site) return;
    if (projectMissing || (openSiteBbl && openSiteBbl !== view.site)) openProject(null);
  }, [view.screen, view.site, openSiteBbl, projectMissing, openProject]);

  useEffect(() => {
    api.layers().then((r) => {
      setLayers(r.data);
      setEnabled(new Set(r.data.filter((l) => l.default_on && l.status !== "error").map((l) => l.layer_id)));
      setSample((s) => s || r.sample);
    });
  }, []);

  // A shared link carries only the BBL; look the address up so the panel can show it and the map can fly
  // there. Search does not match every BBL, so the site profile is the fallback.
  useEffect(() => {
    const bbl = view.site;
    if (!bbl || site?.bbl === bbl) return;
    let live = true;
    api.search(bbl).then(async (r) => {
      const found = r.data.find((x) => x.bbl === bbl);
      if (found) return live && setSite(found);
      const p = await api.siteProfile(bbl);
      if (!live || p.data.bbl !== bbl) return;
      if (p.sample) setSample(true);
      setSite({ label: p.data.address_matched, bbl, bin: p.data.bins[0] ?? null, lat: p.data.lat, lon: p.data.lon });
    });
    return () => {
      live = false;
    };
  }, [view.site, site?.bbl]);

  const toggleLayer = (id: string, on: boolean) =>
    setEnabled((prev) => {
      const next = new Set(prev);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });

  const pickSite = useCallback((result: SearchResult | Picked) => {
    // A new site lets go of the old site's case at once, before the map can frame or draw it.
    setFocusCase(null);
    setSite(result);
    setView({ site: result.bbl, tab: "similar" });
  }, [setView]);

  const shortcuts: Shortcut[] = [
    { keys: ["/", "Mod+k"], label: "Search an address", run: () => setCommandOpen(true), allowInFields: true },
    { keys: ["l"], label: "Show or hide layers", run: () => setView({ layers: !view.layers }) },
    { keys: ["c"], label: "Open or close the conversation", run: () => setView({ chat: !view.chat }) },
    { keys: ["t"], label: "Switch light or dark theme", run: toggleTheme },
    { keys: ["?"], label: "Keyboard shortcuts", run: () => setHelpOpen((o) => !o) },
    {
      keys: ["Escape"],
      label: "Close the top panel",
      run: () => {
        if (helpOpen) setHelpOpen(false);
        else if (view.screen === "project") setView({ screen: "map" });
        else if (view.chat) setView({ chat: false });
        else if (view.site) setView({ site: null });
        else if (view.layers) setView({ layers: false });
      },
    },
  ];
  useShortcuts(commandOpen ? [] : shortcuts);

  const commands: Command[] = [
    { id: "layers", label: view.layers ? "Hide layers" : "Show layers", keys: "L", run: () => setView({ layers: !view.layers }) },
    { id: "chat", label: view.chat ? "Close the conversation" : "Open the conversation", keys: "C", run: () => setView({ chat: !view.chat }) },
    { id: "theme", label: theme === "dark" ? "Switch to light theme" : "Switch to dark theme", keys: "T", run: toggleTheme },
    {
      id: "copy",
      label: "Copy a link to this view",
      hint: "The link opens the same site and panels",
      run: () => void navigator.clipboard?.writeText(window.location.href).catch(() => undefined),
    },
    { id: "help", label: "Keyboard shortcuts", keys: "?", run: () => setHelpOpen(true) },
  ];

  // Behind the project screen, the explorer stays mounted (going back is instant) but out of reach.
  const behind = view.screen === "project";

  return (
    <main className="fs-shell" data-entered={entered} data-site={Boolean(view.site)} data-chat={view.chat} data-layers={view.layers}>
      <div className="fs-shell__map" inert={behind}>
        <CityMap
          site={site && site.bbl === view.site ? site : null}
          onPick={pickSite}
          enabled={enabled}
          onSample={markSample}
          theme={theme}
          focusCaseId={focusCase}
          showAllStrands={allStrands}
          onFocusCase={(caseId) => {
            toggleFocus(caseId);
            setView({ tab: "similar" });
          }}
        />
      </div>

      <div className="fs-shell__left" inert={behind}>
        <header className="fs-topbar fs-panel">
          <span className="fs-brand">
            <img className="fs-brand__logo" src={logo} alt={copy.app.name} />
          </span>
          <button type="button" className="fs-search" onClick={() => setCommandOpen(true)} aria-label="Search an address">
            <SearchIcon width={16} height={16} />
            <span>Search an address</span>
            <Kbd>/</Kbd>
          </button>
          <div className="fs-topbar__tools">
            <Button variant="ghost" className="fs-btn fs-layers-btn" aria-label={`Layers, ${enabled.size} on (${keyLabel("l")})`}
              aria-pressed={view.layers} title="Layers (L)" onClick={() => setView({ layers: !view.layers })}>
              <LayersIcon />
              <span>Layers</span>
              <span className="fs-num fs-layers-btn__count">{enabled.size}</span>
            </Button>
            <Button variant="ghost" size="icon" aria-label={theme === "dark" ? "Light theme (T)" : "Dark theme (T)"} title="Theme (T)" onClick={toggleTheme}>
              {theme === "dark" ? <SunIcon /> : <MoonIcon />}
            </Button>
            <Button variant="ghost" size="icon" aria-label="Keyboard shortcuts (?)" title="Shortcuts (?)" onClick={() => setHelpOpen(true)}>
              <KeyboardIcon />
            </Button>
          </div>
        </header>

        <LayerSlot
          open={view.layers}
          onClose={() => setView({ layers: false })}
          layers={layers}
          enabled={enabled}
          onToggle={toggleLayer}
          hiddenForCase={focusCase !== null}
        />
      </div>

      <div className="fs-shell__right" inert={behind}>
        <SiteSlot
          bbl={view.site}
          site={site}
          onClose={() => {
            setFocusCase(null);
            setView({ site: null, tab: "similar" });
          }}
          tab={view.tab}
          onTab={(tab) => setView({ tab })}
          onContinue={() => setView({ screen: "project" })}
          focusCase={focusCase}
          onFocusCase={toggleFocus}
          allStrands={allStrands}
          onAllStrands={setAllStrands}
        />
      </div>

      <ChatSlot
        open={entered && !behind}
        expanded={view.chat}
        onExpanded={(chat) => setView({ chat })}
        bbl={view.site}
        site={site}
        onPickBbl={(bbl) => setView({ site: bbl, tab: "similar" })}
        onToggleLayer={toggleLayer}
      />

      <div className="fs-shell__bottom" inert={behind}>
        <LimitationsPanel />
        <DataStatus layers={layers} sample={sample} />
      </div>

      {!view.site && !commandOpen && (
        <div className="fs-hint" role="note">
          Press <Kbd>/</Kbd> to find a site, or pick one on the map
        </div>
      )}

      {view.screen === "project" && (
        <ProjectScreen
          bbl={view.site}
          siteLabel={site && site.bbl === view.site ? titleCase(site.label).split(",")[0] : undefined}
          workspace={workspace}
          onProjectCreated={openProject}
          onBack={() => setView({ screen: "map" })}
        />
      )}

      <Intro onDone={enter} />

      <CommandBar open={commandOpen} onClose={() => setCommandOpen(false)} onPickSite={pickSite} commands={commands} />
      <ShortcutsHelp open={helpOpen} onClose={() => setHelpOpen(false)} shortcuts={shortcuts} />
    </main>
  );
}
