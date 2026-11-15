// The panels the shell hosts, each in a frame the reader can move, resize, minimise and maximise
// (MapWindow.tsx). Each is a slot with a working interim body so the shell can be judged on
// fixtures now; the owners' PRs replace the bodies, not the frames:
//   LayerSlot   -> Shandon's layer panel (PR 5)
//   SiteSlot    -> Camilo's site, similar-case and action panels (PR 10, filled)
//   ChatSlot    -> Jahleel's chat panel (PR 9, filled)
import type { CSSProperties } from "react";

import type { LayerCatalogEntry, SearchResult } from "../contracts";
import { copy } from "../copy";
import {
  Badge,
  Button,
  Count,
  EmptyState,
  ErrorState,
  formatDate,
  HAZARD_LABELS,
  SampleBadge,
  Skeleton,
  SkeletonCard,
  SourceLabel,
  Toggle,
} from "../design";
import { ChatDock } from "../features/chat/ChatDock";
import { SitePanel, useSiteData, type SiteTab } from "../features/site_panel/SitePanel";
import { titleCase } from "./CommandBar";
import { MapWindow } from "./MapWindow";

// A maximised panel stops above the bottom row, so the limitations line and the question box stay in view.
const ABOVE_THE_BOTTOM_ROW = { bottom: "calc(var(--fs-dock-bottom) + var(--fs-dock-h) + var(--fs-4))" };

// ---- Layers --------------------------------------------------------------------------------------

type LayerSlotProps = {
  open: boolean;
  onClose: () => void;
  layers: LayerCatalogEntry[] | null;
  enabled: Set<string>;
  onToggle: (id: string, on: boolean) => void;
  /** A similar case is shown on the map, so the record layers are hidden until it is let go. */
  hiddenForCase?: boolean;
};

export function LayerSlot({ open, onClose, layers, enabled, onToggle, hiddenForCase }: LayerSlotProps) {
  const usable = layers?.filter((l) => l.status !== "error") ?? [];
  const allOn = usable.length > 0 && usable.every((l) => enabled.has(l.layer_id));
  const onCount = usable.filter((l) => enabled.has(l.layer_id)).length;
  return (
    <MapWindow
      id="layers"
      title="Layers"
      subtitle="Public data by hazard. Off means filtered, not deleted."
      open={open}
      edge="left"
      onClose={onClose}
      className="fs-shell__layers"
      label="Layers"
      maximizedInset={ABOVE_THE_BOTTOM_ROW}
    >
      {layers === null && (
        <>
          <SkeletonCard lines={1} />
          <SkeletonCard lines={1} />
          <SkeletonCard lines={1} />
        </>
      )}
      {hiddenForCase && (
        <p className="fs-quiet" role="status">Layers are hidden while a similar case is shown. Click the case again to bring them back.</p>
      )}
      {layers?.length === 0 && <EmptyState title="No layers yet">The layer catalog came back empty.</EmptyState>}
      {usable.length > 1 && (
        <div className="fs-layer fs-layer--all">
          <Toggle
            checked={allOn}
            onChange={(on) => usable.forEach((l) => onToggle(l.layer_id, on))}
            label={<span className="fs-layer__name">All layers</span>}
            hint={`${onCount} of ${usable.length} on`}
          />
        </div>
      )}
      {layers?.map((layer) => (
        <div key={layer.layer_id} className="fs-layer" style={{ "--fs-hz": `var(--fs-hz-${layer.hazard})` } as CSSProperties}>
          {layer.status === "error" ? (
            <ErrorState title={`${layer.name}: ${copy.queryStatus.error.toLowerCase()}`}>{copy.states.couldntLoad}</ErrorState>
          ) : (
            <Toggle
              checked={enabled.has(layer.layer_id)}
              onChange={(on) => onToggle(layer.layer_id, on)}
              label={
                <span className="fs-layer__name">
                  <span className="fs-chip__dot" aria-hidden="true" />
                  {layer.name}
                </span>
              }
              hint={
                <>
                  {HAZARD_LABELS[layer.hazard]} · <Count value={layer.feature_count} status={layer.status} />
                </>
              }
            />
          )}
          <SourceLabel name={layer.source_name} url={layer.source_url} date={layer.updated_at} />
        </div>
      ))}
    </MapWindow>
  );
}

// ---- Site ----------------------------------------------------------------------------------------

type SiteSlotProps = {
  bbl: string | null;
  site: SearchResult | null;
  onClose: () => void;
  tab: SiteTab;
  onTab: (tab: SiteTab) => void;
  /** Opens the full-screen project view for this site. */
  onContinue: () => void;
  focusCase: string | null;
  onFocusCase: (caseId: string) => void;
  allStrands: boolean;
  onAllStrands: (on: boolean) => void;
};

export function SiteSlot({ bbl, site, onClose, tab, onTab, onContinue, focusCase, onFocusCase, allStrands, onAllStrands }: SiteSlotProps) {
  const open = Boolean(bbl);
  const data = useSiteData(bbl);
  return (
    <MapWindow
      id="site"
      title={site ? titleCase(site.label).split(",")[0] : bbl ? <Skeleton width={180} height={14} /> : "Site"}
      subtitle={
        site ? (
          <span className="fs-num">
            {titleCase(site.label).split(",").slice(1).join(",").trim()} · BBL {site.bbl}
            {site.bin ? ` · BIN ${site.bin}` : ""}
          </span>
        ) : undefined
      }
      open={open}
      edge="right"
      onClose={onClose}
      className="fs-shell__site"
      label="Site"
      maximizedInset={ABOVE_THE_BOTTOM_ROW}
    >
      {open && (
        <>
          <Button variant="primary" className="fs-btn fs-site__continue" onClick={onContinue}>
            Continue to project →
          </Button>
          <SitePanel bbl={bbl ?? ""} data={data} tab={tab} onTab={onTab} onStart={onContinue}
            strands={{ focusedId: focusCase, onFocus: onFocusCase, all: allStrands, onAll: onAllStrands }} />
        </>
      )}
    </MapWindow>
  );
}

// ---- Chat ----------------------------------------------------------------------------------------

type ChatSlotProps = {
  /** False while something else has the screen (the opening, the project screen): the dock steps away. */
  open?: boolean;
  /** The conversation is open above the question box; closed, the box alone stays on screen. */
  expanded: boolean;
  onExpanded: (expanded: boolean) => void;
  bbl: string | null;
  site: SearchResult | null;
  onPickBbl: (bbl: string) => void;
  onToggleLayer: (id: string, on: boolean) => void;
};

// The chat's dock, bottom centre: the question box is always on screen, and the conversation opens above
// it once something is asked. It starts minimal; maximised, it shows everything (tabs, examples, notes).
// The body stays mounted in every state, so the conversation survives.
export function ChatSlot({ open = true, expanded, onExpanded, bbl, site, onPickBbl, onToggleLayer }: ChatSlotProps) {
  return (
    <MapWindow
      id="chat"
      title={copy.chat.title}
      edge="bottom"
      className="fs-shell__chat"
      label="Chat"
      open={open}
      minimized={!expanded}
      onMinimized={(minimized) => onExpanded(!minimized)}
      barWhenMinimized
      maximizedInset={ABOVE_THE_BOTTOM_ROW}
    >
      {(frame) => (
        <ChatDock
          detail={frame.minimized ? "bar" : frame.maximized ? "full" : "minimal"}
          onActivate={() => !expanded && onExpanded(true)}
          bbl={bbl}
          siteLabel={site ? titleCase(site.label).split(",")[0] : undefined}
          onFlyTo={(target) => target.bbl && onPickBbl(target.bbl)}
          onToggleLayer={onToggleLayer}
        />
      )}
    </MapWindow>
  );
}

// ---- Status line ---------------------------------------------------------------------------------

export function DataStatus({ layers, sample }: { layers: LayerCatalogEntry[] | null; sample: boolean }) {
  if (!layers) return null;
  const failed = layers.filter((l) => l.status === "error").length;
  const newest = layers.map((l) => l.updated_at).filter(Boolean).sort().pop();
  return (
    <div className="fs-status" role="status">
      {sample && <SampleBadge />}
      {failed > 0 && (
        <Badge tone="error" title={copy.states.couldntLoad}>
          {failed} layer{failed > 1 ? "s" : ""}: {copy.queryStatus.error.toLowerCase()}
        </Badge>
      )}
      {newest && <span className="fs-num">Data as of {formatDate(newest)}</span>}
    </div>
  );
}
