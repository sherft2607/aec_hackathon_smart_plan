// Command bar: opens on "/" or Cmd/Ctrl-K. Type an address to pick a site, or run an app command.
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";

import { api } from "../api/client";
import type { SearchResult } from "../contracts";
import { copy } from "../copy";
import { Badge, Kbd, PinIcon, SearchIcon, Skeleton } from "../design";

export type Command = { id: string; label: string; hint?: string; keys?: string; run: () => void };

type Props = {
  open: boolean;
  onClose: () => void;
  onPickSite: (result: SearchResult) => void;
  commands: Command[];
};

type Item = { kind: "site"; result: SearchResult } | { kind: "command"; command: Command };

export function CommandBar({ open, onClose, onPickSite, commands }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [sample, setSample] = useState(false);
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActive(0);
    requestAnimationFrame(() => input.current?.focus());
  }, [open]);

  // Debounced address search. The fixture fallback returns the same two demo addresses for any query.
  useEffect(() => {
    if (!open) return;
    const q = query.trim();
    if (q.length < 2) {
      setResults([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    let live = true;
    const timer = window.setTimeout(() => {
      api.search(q).then((r) => {
        if (!live) return;
        setResults(r.data);
        setSample(r.sample);
        setLoading(false);
      });
    }, 160);
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
  }, [query, open]);

  const items = useMemo<Item[]>(() => {
    const q = query.trim().toLowerCase();
    const cmds = commands.filter((c) => !q || c.label.toLowerCase().includes(q));
    return [...results.map((result) => ({ kind: "site" as const, result })), ...cmds.map((command) => ({ kind: "command" as const, command }))];
  }, [results, commands, query]);

  useEffect(() => setActive((a) => Math.min(a, Math.max(items.length - 1, 0))), [items.length]);

  const choose = (item: Item | undefined) => {
    if (!item) return;
    onClose();
    if (item.kind === "site") onPickSite(item.result);
    else item.command.run();
  };

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => (items.length ? (a + 1) % items.length : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => (items.length ? (a - 1 + items.length) % items.length : 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(items[active]);
    } else if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  };

  if (!open) return null;

  return (
    <div className="fs-cmd-scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="fs-cmd fs-panel" role="dialog" aria-modal="true" aria-label="Search and commands">
        <div className="fs-cmd__field">
          <SearchIcon width={18} height={18} />
          <input
            ref={input}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search an NYC address or BBL, or type a command"
            aria-label="Search an address or BBL"
            aria-controls="fs-cmd-list"
            aria-activedescendant={items[active] ? `fs-cmd-${active}` : undefined}
            role="combobox"
            aria-expanded={items.length > 0}
            spellCheck={false}
            autoComplete="off"
          />
          {sample && results.length > 0 && <Badge tone="sample" title={copy.app.sampleDataHint}>{copy.app.sampleData}</Badge>}
          <Kbd>Esc</Kbd>
        </div>

        <ul className="fs-cmd__list" id="fs-cmd-list" role="listbox">
          {loading && (
            <li className="fs-cmd__loading" aria-hidden="true">
              <Skeleton width="70%" height={14} />
              <Skeleton width="45%" height={10} />
            </li>
          )}
          {!loading && query.trim().length >= 2 && results.length === 0 && (
            <li className="fs-cmd__empty">{copy.map.searchNoResults}</li>
          )}
          {items.map((item, i) => (
            <li
              key={item.kind === "site" ? `s-${i}-${item.result.bbl}-${item.result.label}` : `c-${item.command.id}`}
              id={`fs-cmd-${i}`}
              role="option"
              aria-selected={i === active}
              className="fs-cmd__item"
              onMouseMove={() => setActive(i)}
              onClick={() => choose(item)}
            >
              {item.kind === "site" ? (
                <>
                  <PinIcon width={16} height={16} />
                  <span className="fs-cmd__label">
                    {titleCase(item.result.label)}
                    <span className="fs-cmd__hint fs-num">BBL {item.result.bbl}</span>
                  </span>
                  <span className="fs-cmd__go">Open site</span>
                </>
              ) : (
                <>
                  <span className="fs-cmd__icon" aria-hidden="true">›</span>
                  <span className="fs-cmd__label">
                    {item.command.label}
                    {item.command.hint && <span className="fs-cmd__hint">{item.command.hint}</span>}
                  </span>
                  {item.command.keys && <Kbd>{item.command.keys}</Kbd>}
                </>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/** "2625 BEDFORD AVENUE, Brooklyn" -> "2625 Bedford Avenue, Brooklyn". Geocoder labels arrive in caps. */
export function titleCase(label: string) {
  return label.replace(/, USA$/, "").replace(/\b([A-Z])([A-Z]{2,})\b/g, (_, a: string, b: string) => a + b.toLowerCase());
}
