// A panel over the map that the reader can move, resize, minimise and maximise. It draws the same frame
// as the design system's Panel (same classes), so a slot's body does not change. The body stays mounted
// in every state, so a conversation or a scroll position survives a minimise.
import { useState } from "react";
import type { ReactNode } from "react";

import { Button, CloseIcon } from "../design";
import { useMapWindow, type MaximizedInset, type WindowEdges } from "./map_window";
import "./map_window.css";

type MapWindowProps = {
  /** Unique among the panels: it keeps this one's place in the front-to-back order. */
  id: string;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  onClose?: () => void;
  /** A function is handed the frame's state, for a body that draws less in a smaller frame. */
  children: ReactNode | ((frame: MapWindowFrame) => ReactNode);
  className?: string;
  open?: boolean;
  edge?: "left" | "right" | "bottom";
  label?: string;
  /** Pass both to hold the minimised state outside the panel (the chat's lives in the URL). */
  minimized?: boolean;
  onMinimized?: (minimized: boolean) => void;
  /** Minimised, show the body as a one-line bar in place of the title bar (the chat's question box). */
  barWhenMinimized?: boolean;
  maximizedInset?: MaximizedInset;
};

export type MapWindowFrame = { minimized: boolean; maximized: boolean };

const HANDLES: { name: string; edges: WindowEdges }[] = [
  { name: "n", edges: { top: true } },
  { name: "s", edges: { bottom: true } },
  { name: "e", edges: { right: true } },
  { name: "w", edges: { left: true } },
  { name: "ne", edges: { top: true, right: true } },
  { name: "nw", edges: { top: true, left: true } },
  { name: "se", edges: { bottom: true, right: true } },
  { name: "sw", edges: { bottom: true, left: true } },
];

const MINIMISE = "M3.5 12.5h9";
const MAXIMISE = "M3.5 3.5h9v9h-9z";
const RESTORE = "M5.5 5.5v-2h7v7h-2M3.5 5.5h7v7h-7z";
const OPEN_UP = "M4 10l4-4 4 4";
const PUT_BACK = "M12.5 3.5l-6 6M6.5 5v4.5H11";
const GRIP = "M6 4h.01M10 4h.01M6 8h.01M10 8h.01M6 12h.01M10 12h.01";

function Glyph({ d, dots = false }: { d: string; dots?: boolean }) {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" strokeWidth={dots ? 2 : 1.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

export function MapWindow(props: MapWindowProps) {
  const { id, title, subtitle, actions, onClose, children, className, open = true, edge = "left", label, barWhenMinimized = false } = props;
  const [ownMinimized, setOwnMinimized] = useState(false);
  const minimized = props.minimized ?? ownMinimized;
  const setMinimized = props.onMinimized ?? setOwnMinimized;
  const win = useMapWindow(id, minimized, props.maximizedInset);
  const asBar = minimized && barWhenMinimized;

  return (
    <section
      ref={win.ref}
      className={`fs-panel fs-slide fs-win ${className ?? ""}`}
      style={win.style}
      data-open={open}
      data-edge={edge}
      data-min={minimized}
      data-bar={asBar}
      data-max={win.maximized}
      data-moved={win.moved}
      aria-label={label}
      aria-hidden={!open}
      inert={!open}
      onPointerDownCapture={win.raise}
    >
      {!asBar && (
        <header className="fs-panel__head fs-win__head" data-drag={win.canDrag} onPointerDown={win.startMove} onDoubleClick={win.putBack}>
          <h2 className="fs-panel__title">
            {title}
            {subtitle && <span className="fs-panel__sub">{subtitle}</span>}
          </h2>
          {actions}
          {win.moved && !win.maximized && (
            <Button variant="ghost" size="icon" onClick={win.putBack} aria-label="Put this panel back in its place" title="Put back in its place">
              <Glyph d={PUT_BACK} />
            </Button>
          )}
          <Button variant="ghost" size="icon" onClick={() => setMinimized(!minimized)} aria-label={minimized ? "Restore this panel" : "Minimise this panel"} title={minimized ? "Restore" : "Minimise"}>
            <Glyph d={minimized ? OPEN_UP : MINIMISE} />
          </Button>
          {!minimized && (
            <Button variant="ghost" size="icon" className="fs-btn fs-win__max" onClick={win.toggleMaximized} aria-label={win.maximized ? "Restore this panel's size" : "Maximise this panel"} title={win.maximized ? "Restore size" : "Maximise"}>
              <Glyph d={win.maximized ? RESTORE : MAXIMISE} />
            </Button>
          )}
          {onClose && (
            <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close panel" title="Close">
              <CloseIcon />
            </Button>
          )}
        </header>
      )}
      {/* The three children keep their places in both states, so the body is never remounted. */}
      <div className="fs-win__row">
        {asBar && (
          <span className="fs-win__grip" data-drag={win.canDrag} onPointerDown={win.startMove} title="Drag to move">
            <Glyph d={GRIP} dots />
          </span>
        )}
        <div className="fs-panel__body" hidden={minimized && !asBar}>
          {typeof children === "function" ? children({ minimized, maximized: win.maximized }) : children}
        </div>
        {asBar && (
          <Button variant="ghost" size="icon" onClick={() => setMinimized(false)} aria-label="Open this panel" title="Open">
            <Glyph d={OPEN_UP} />
          </Button>
        )}
      </div>
      {win.canResize &&
        HANDLES.map((handle) => (
          <span key={handle.name} className="fs-win__resize" data-edge={handle.name} aria-hidden="true" onPointerDown={(event) => win.startResize(event, handle.edges)} />
        ))}
    </section>
  );
}
