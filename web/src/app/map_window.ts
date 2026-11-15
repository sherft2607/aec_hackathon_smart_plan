// Where one panel over the map sits once the reader has moved or resized it, and which panel is in front.
// A panel that was never moved has no rectangle here: it stays where the shell's stylesheet docks it.
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import type { CSSProperties, PointerEvent as ReactPointerEvent } from "react";

export type WindowRect = { x: number; y: number; w: number; h: number };
export type WindowEdges = { left?: boolean; top?: boolean; right?: boolean; bottom?: boolean };
/** How far a maximised panel stays from the screen's left and bottom edges (a CSS length). */
export type MaximizedInset = { left?: string; bottom?: string };

const MIN_WIDTH = 300;
const MIN_HEIGHT = 200;
const KEPT_ON_SCREEN = 72; // of a panel's width, so its title bar can always be reached
const HEAD_HEIGHT = 48;
const RESTORED_HEIGHT = 480; // for a panel first moved while minimised: it has no height of its own yet
// Pointer travel (across plus down, in pixels) under which a press leaves the panel as it is. As thick
// as a resize strip (map_window.css): a wobble inside the strip that was pressed resizes nothing, and
// a double-click on a title bar, which puts a panel back, does not undock it first.
const DRAG_STARTS_AT = 5;
const NARROW_SCREEN = "(max-width: 860px)"; // the shell's sheet layout: panels stay docked there
const NOT_A_HANDLE = "button, a, input, textarea, select, [role='tab']";

function fitToScreen(rect: WindowRect): WindowRect {
  const { innerWidth, innerHeight } = window;
  const w = Math.min(Math.max(rect.w, MIN_WIDTH), innerWidth);
  const h = Math.min(Math.max(rect.h, MIN_HEIGHT), innerHeight);
  return {
    w,
    h,
    x: Math.min(Math.max(rect.x, KEPT_ON_SCREEN - w), innerWidth - KEPT_ON_SCREEN),
    y: Math.min(Math.max(rect.y, 0), innerHeight - HEAD_HEIGHT),
  };
}

function resized(start: WindowRect, edges: WindowEdges, dx: number, dy: number): WindowRect {
  let { x, y, w, h } = start;
  if (edges.right) w = start.w + dx;
  if (edges.bottom) h = start.h + dy;
  if (edges.left) {
    w = Math.max(MIN_WIDTH, start.w - dx);
    x = start.x + start.w - w; // the right edge stays put
  }
  if (edges.top) {
    y = Math.max(0, Math.min(start.y + dy, start.y + start.h - MIN_HEIGHT));
    h = start.y + start.h - y; // the bottom edge stays put
  }
  return { x, y, w, h };
}

// ---- which panel is in front: the one last touched, shared by every panel -----------------------

let frontOrder: string[] = [];
const orderListeners = new Set<() => void>();

function bringToFront(id: string) {
  if (frontOrder[frontOrder.length - 1] === id) return;
  frontOrder = [...frontOrder.filter((other) => other !== id), id];
  orderListeners.forEach((listener) => listener());
}

function subscribeToOrder(listener: () => void) {
  orderListeners.add(listener);
  return () => void orderListeners.delete(listener);
}

function subscribeToNarrow(listener: () => void) {
  const query = window.matchMedia(NARROW_SCREEN);
  query.addEventListener("change", listener);
  return () => query.removeEventListener("change", listener);
}

// ---- one panel -----------------------------------------------------------------------------------

export function useMapWindow(id: string, minimized: boolean, maximizedInset: MaximizedInset = {}) {
  const ref = useRef<HTMLElement>(null);
  const [rect, setRect] = useState<WindowRect | null>(null);
  const [wantsMaximized, setMaximized] = useState(false);
  const place = useSyncExternalStore(subscribeToOrder, () => frontOrder.indexOf(id));
  const narrow = useSyncExternalStore(subscribeToNarrow, () => window.matchMedia(NARROW_SCREEN).matches);
  const maximized = wantsMaximized && !minimized && !narrow;

  useEffect(() => {
    const refit = () => setRect((current) => current && fitToScreen(current));
    window.addEventListener("resize", refit);
    return () => window.removeEventListener("resize", refit);
  }, []);

  /** `edges` null moves the panel; otherwise those edges follow the pointer. */
  const startDrag = useCallback(
    (event: ReactPointerEvent, edges: WindowEdges | null) => {
      const element = ref.current;
      if (event.button !== 0 || narrow || maximized || !element) return;
      if (!edges && (event.target as HTMLElement).closest(NOT_A_HANDLE)) return;
      const box = element.getBoundingClientRect();
      const start = { x: box.left, y: box.top, w: box.width, h: minimized ? (rect?.h ?? RESTORED_HEIGHT) : box.height };
      const from = { x: event.clientX, y: event.clientY };
      let dragging = false;
      const onMove = (moved: PointerEvent) => {
        const dx = moved.clientX - from.x;
        const dy = moved.clientY - from.y;
        if (!dragging && Math.abs(dx) + Math.abs(dy) < DRAG_STARTS_AT) return;
        dragging = true;
        setRect(fitToScreen(edges ? resized(start, edges, dx, dy) : { ...start, x: start.x + dx, y: start.y + dy }));
      };
      const onEnd = () => {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onEnd);
        window.removeEventListener("pointercancel", onEnd);
        document.body.style.userSelect = "";
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onEnd);
      window.addEventListener("pointercancel", onEnd);
      document.body.style.userSelect = "none"; // a drag across the panels must not select their text
    },
    [maximized, minimized, narrow, rect],
  );

  const zIndex = `calc(var(--fs-z-panel) + ${place + 1})`;
  const free = { right: "auto", bottom: "auto", maxWidth: "none", maxHeight: "none", margin: 0 } as const;
  let style: CSSProperties = { zIndex };
  if (maximized) {
    style = {
      ...free,
      position: "fixed",
      top: "var(--fs-4)",
      right: "var(--fs-4)",
      left: maximizedInset.left ?? "var(--fs-4)",
      bottom: maximizedInset.bottom ?? "var(--fs-4)",
      width: "auto",
      height: "auto",
      zIndex,
    };
  } else if (rect && !narrow) {
    style = { ...free, position: "fixed", left: rect.x, top: rect.y, width: rect.w, height: minimized ? "auto" : rect.h, zIndex };
  }

  return {
    ref,
    style,
    maximized,
    /** Moved or resized away from its docked place. */
    moved: rect !== null && !narrow,
    canDrag: !narrow && !maximized,
    canResize: !narrow && !maximized && !minimized,
    startMove: (event: ReactPointerEvent) => startDrag(event, null),
    startResize: (event: ReactPointerEvent, edges: WindowEdges) => startDrag(event, edges),
    toggleMaximized: () => setMaximized((on) => !on),
    putBack: () => {
      setRect(null);
      setMaximized(false);
    },
    raise: () => bringToFront(id),
  };
}
