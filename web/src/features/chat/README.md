Docked chat. Owner: Jahleel (PR 4, 9).

Questions about one site, answered in parts that each say where they came from. The server decides
each part's kind from what the part rests on; this folder only shows it.

## Where it sits

The shell's chat slot (`web/src/app/slots.tsx`, `ChatSlot`) draws the frame and renders `ChatDock`
inside it: two tabs, "Ask" (the chat) and "Project" (the workspace in `../project`). Both stay mounted,
so switching tabs keeps the conversation. `ChatDock` passes the picked site, the open project, `onPin`
from `useProject`, and the shell's two handlers: a fly-to that names a lot opens that lot as the site,
and a layer switch changes the shell's layer set. An answer's own fly-to is carried out only for the
open site: for another lot the panel says the map stayed put, because a new site starts a new
conversation and the answer would be lost. The reader can still open that lot from a source button,
which says it starts a new conversation. A fly-to with only coordinates (a past case with no
lot) does nothing yet.

The slot is a bar centred along the map's lower edge. It tells `ChatDock` how much to draw (`detail`):

| `detail` | When | What is drawn |
|---|---|---|
| `bar` | Closed (the default) | The question box alone, on one line. The conversation stays mounted behind it |
| `minimal` | Open | The conversation above the box, once there is one. No tabs, opening text, examples or note |
| `full` | Maximised | Everything: the Ask and Project tabs, the site line, the opening text, the example questions and the note under the box |

Asking a question calls `onActivate`, and the shell opens the conversation above the box. The Project
tab is reached only from the full view.

With a live model, a question goes out twice at once (`chat_client.ts`): `askChat` for the full answer
and `askChatFirst` for the server's quick first answer, which is shown only while the question is still
waiting and is replaced by the full one. It is not kept: history and pins use answered exchanges only.

`ChatPanel` with `embedded` renders only the conversation and the question box, for a frame someone
else draws. Without it, it is a self-contained dock:

```tsx
import { ChatPanel } from "../features/chat/ChatPanel";

<ChatPanel
  bbl={siteBbl}                      // null until a site is picked: the input then says why it is off
  siteLabel="2625 Bedford Avenue"    // optional
  projectId={openProjectId}          // optional: with it, answers can be pinned
  asOf={asOfDay}                     // optional YYYY-MM-DD, when the page replays an earlier date
  jobType={jobType} stage={stage}    // optional
  onFlyTo={(target) => ...}          // { ref?, label?, bbl?, lat?, lon? }: bbl, or lat and lon, is set
  onToggleLayer={(layerId, on) => ...}
  onPin={workspace.pinChatAnswer}    // from useProject (../project); gets { title, question, as_of, offline, answer_parts, text }
/>
```

On its own, the panel docks bottom right over the map and collapses to its title bar; pass `className`
to place it elsewhere.

The handlers are how the chat acts on the page. An answer can carry actions (show or hide a layer, fly
the map, pin an answer); the panel runs them in order through the handlers and says so in the answer
when the page has no handler for one. A source chip under a part opens the source in a new tab, and
"Show on the map" calls `onFlyTo`. `onPin` may return a promise; if it rejects, the panel shows the
error's message next to the answer.

A conversation is about one site on one day: changing `bbl` or `asOf` starts a new one, so answers
from today's view are never sent as context to a question about an earlier date.

## Files

| File | What it holds |
| --- | --- |
| `ChatDock.tsx` | What the shell's chat slot renders: the chat and the project workspace as two tabs |
| `ChatPanel.tsx` | The conversation and the question box; a dock of its own when not `embedded` |
| `ChatAnswerParts.tsx` | One answer: each part under its source label, with its source chips |
| `chat_part_kinds.ts` | The label and the colour for each kind of part, from the design system's tokens |
| `chat_theme.css` | Points the placeholder colour names at the design system's tokens inside these two panels |
| `chat_client.ts` | `POST /api/chat` and `GET /api/chat/setup` |
| `chat_conversation.ts` | The exchanges kept, and the earlier ones a follow-up sends within the server's caps |
| `chat_page_actions.ts` | Running an answer's actions; where a source chip flies the map |
| `chat_saved_answers.ts`, `chat_saved_answers.json` | Answers saved ahead of time for the sample site |

## When the server has no key, or there is no server

- **No model key on the server:** the server still answers, from the site's data, by matching the
  question to a search, a count, the warnings, the action items or the closest cases. Each such
  answer says no model was called.
- **No server at all:** this chat does not use the shared client's fixture fallback, because a fixed
  answer under a question it was not written for would read as the answer. It says the question was
  not answered and offers the saved answers, which are shown only for the site they were written for
  and never in an as-of view.

`chat_saved_answers.json` is generated: `python -m api.routers.chat.chat_saved_answers_export`. A
test fails when it is out of date.

## Limits

- The colours are the design system's, through `chat_theme.css`; the layout is still this folder's own
  classes, not the design system's card, chip and source label components.
- The part labels are this folder's (`chat_part_kinds.ts`), not `copy.sourceLabels`: they carry the
  qualifiers ("not checked by us", "a pattern, not a prediction") the short labels leave out.
- A single record's chip flies to the site, since an answer part does not carry the record's own lot.
- No test runner is set up in `web/` yet, so this folder is covered by the type check and a browser check only.
