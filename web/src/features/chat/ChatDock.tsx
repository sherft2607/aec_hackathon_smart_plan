// What fills the shell's chat slot: the chat and the project workspace, as two tabs inside the one
// frame the shell draws. Both stay mounted, so switching tabs keeps the conversation. How much is drawn
// follows the frame (`detail`): the question box alone, the conversation with it, or everything.
import { useState } from "react";

import { copy } from "../../copy";
import { Tabs } from "../../design";
import { ProjectPanel } from "../project/ProjectPanel";
import { useProjectIdInUrl } from "../project/project_url";
import { useProject } from "../project/useProject";
import { ChatPanel } from "./ChatPanel";
import type { ChatPageHandlers } from "./chat_page_actions";

type DockTab = "ask" | "project";

/** bar: the question box alone. minimal: the conversation and the box. full: tabs, examples and notes too. */
export type ChatDetail = "bar" | "minimal" | "full";

type ChatDockProps = Pick<ChatPageHandlers, "onFlyTo" | "onToggleLayer"> & {
  bbl: string | null;
  siteLabel?: string;
  detail?: ChatDetail;
  /** The reader asked something: the slot should open the conversation. */
  onActivate?: () => void;
};

export function ChatDock({ bbl, siteLabel, onFlyTo, onToggleLayer, detail = "full", onActivate }: ChatDockProps) {
  const [tab, setTab] = useState<DockTab>("ask");
  const [projectId, openProject] = useProjectIdInUrl();
  const workspace = useProject(projectId);
  // An answer is pinned only to a project the store really holds.
  const canPin = workspace.state.status === "ok" && !workspace.state.sample;
  const full = detail === "full";
  const showAsk = !full || tab === "ask"; // the project tab is reached from the full view
  return (
    // One wrapper in every state, so the panels below are never remounted. Full, the column is kept readable.
    <div className={`flex min-h-0 flex-1 flex-col gap-3 ${full ? "mx-auto w-full max-w-3xl" : ""}`}>
      {full && (
        <Tabs<DockTab>
          label="Chat and project"
          value={tab}
          onChange={setTab}
          options={[
            { value: "ask", label: "Ask" },
            { value: "project", label: copy.project.title },
          ]}
        />
      )}
      <div className={showAsk ? "flex min-h-0 flex-1 flex-col" : "hidden"}>
        <ChatPanel
          embedded
          detail={detail}
          onActivate={onActivate}
          bbl={bbl}
          siteLabel={siteLabel}
          projectId={canPin ? projectId : null}
          onFlyTo={onFlyTo}
          onToggleLayer={onToggleLayer}
          onPin={workspace.pinChatAnswer}
        />
      </div>
      <div className={!showAsk ? "min-h-0 flex-1 overflow-y-auto" : "hidden"}>
        <ProjectPanel embedded workspace={workspace} siteBbl={bbl} siteLabel={siteLabel} onProjectCreated={openProject} />
      </div>
    </div>
  );
}
