// The open project lives in the URL (?project=<id>), next to the shell's own keys, so the architect can
// send the link and the structural engineer opens the same project. The shell's url_state.ts rewrites
// only its own keys, so this one is kept across its updates.
import { useCallback, useEffect, useState } from "react";

const KEY = "project";
const CHANGED = "foresite:project-changed";
const read = () => new URLSearchParams(window.location.search).get(KEY);

export function useProjectIdInUrl(): [string | null, (projectId: string | null) => void] {
  const [projectId, setProjectId] = useState<string | null>(read);

  // The project screen and the chat dock each hold this hook; a project opened in one reaches the other.
  useEffect(() => {
    const onPop = () => setProjectId(read());
    window.addEventListener("popstate", onPop);
    window.addEventListener(CHANGED, onPop);
    return () => {
      window.removeEventListener("popstate", onPop);
      window.removeEventListener(CHANGED, onPop);
    };
  }, []);

  const open = useCallback((next: string | null) => {
    const query = new URLSearchParams(window.location.search);
    if (next) query.set(KEY, next);
    else query.delete(KEY);
    const search = query.toString();
    window.history.replaceState(null, "", `${window.location.pathname}${search ? `?${search}` : ""}${window.location.hash}`);
    setProjectId(next);
    window.dispatchEvent(new Event(CHANGED));
  }, []);

  return [projectId, open];
}
