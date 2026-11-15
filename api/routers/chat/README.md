# ForeSite chat

`POST /api/chat`: a question about one site, answered in **parts** that each say where they came
from, plus **actions** for the page to carry out. Ported from the reference in `jahleel/api/chat/`
(its README explains the design at length); this file covers what is different here.

**State: wired in.** `POST /api/chat` in `api/main.py` is this chat, replacing the stub, and it
returns the shared contract's `ChatResponse`. It reads each site part through the function that
part's route answers from (PR 4), so it shows real data as soon as an owner's module lands and the
labelled sample until then. No contract carries a site's list of records, so a record search
answers "unknown", not "none found". Live answers: see "Live and mock" below.

The contract's `ai_suggestion` and `user_input` kinds are not produced: every part here rests on a
source or is a fixed server line.

## What an answer holds

| Part kind | Rests on | Label for the reader |
|---|---|---|
| `record` | a public record, a dataset count, the site's facts | From the public record |
| `case` | past cases compared with this site | From the case library, as publicly reported |
| `warning` | an early-warning rule's result | An early-warning pattern, not a prediction |
| `action` | an action item from the action rules | An action item, not a determination |
| `lead` | a web search result | From the web, not checked by us |
| `not_found` | looked for and nothing found, with what was searched | Not found |
| `unknown` | a query or a load failed: nothing is known | Unknown. This is not zero |
| `notice` | a fixed line the server writes | (small print) |

On the wire these are the contract's kinds (`record` is `public_record`, `lead` is `web`), with a
part's first source in `source_name`, `source_url` and `record_id` (`chat_contract_map.py`).

The model never chooses a kind: the server derives it from the ids a statement cites, and a
statement citing two kinds of source is held back. Counts, search results, "none found" and
"unknown" are written by the server, for a dataset and for the site's early warnings and action
items alike: a list that did not load is unknown, never none. A statement is also held back for a number that is not in its
source, a verdict, blame, a cause (except a past case's or a web result's, as reported), a
prediction, or a company name. One correction round, then what still fails is dropped and said.

**Actions** (`ChatAnswer.actions`), each checked before it is returned:
- `toggle_layer`: only a layer id the layer list has.
- `fly_to`: only an item of this view with a place (the site, a neighbor, a record, a case).
- `pin_answer` (`pin` on the wire): only with an open project (`project_id` in the request). `target`
  is `this` or `previous`. The chat writes nothing itself: the page saves the pin, as the person signed in.

**As-of:** a record, past case or warning dated on or after the day is not in the view, the searches
or the model's reading text; neither is text added later or today's status; web search is off.

**Mock mode:** a typed question is matched by keyword to a search, a count, the warnings, the action
items or a page action, through the same checks, and is labeled as a mock. A question nothing matches
is answered with a line saying so and what the mock can do; it never makes an answer up.

**No server:** the web chat panel shows answers saved ahead of time for the sample site
(`chat_saved_answers_export.py` writes them into `web/src/features/chat/`, built from the site's data
through the same checks and labeled as saved). They are redone for the demo sites once those are picked.

## Live and mock

**State.** The integrator reported on 2026-11-14 that a key is set on the demo host and the chat
answered live there (the closing note on pull request #28). Without a key the chat answers in mock
mode; with no server the web panel offers saved answers. Each says so on the answer.

**What a live run has checked.** On 2026-11-14, six questions were asked on screen for the sample site
(lot 3052110074), in the web app against a local server with a key, no as-of day:

| Question | Seconds | What came back |
|---|---|---|
| What early warnings are there for this site? | 28 | The server's count (4) and the four rule results in the model's words, each on its rule |
| What happened next door? | 34 | Past case as publicly reported (cause "under investigation"), quoted records, one warning, and a fly-to for the touching lot |
| Summarize the main risks at this site | 44 | Record, warning, past-case and action-item parts, with the not-advice notice |
| How many ECB violations are on file? | 15 | The server's count (4), the three violations the profile names, and a gap for the full list |
| Who owns this building? | 6 | The names-withheld notice and the lot's facts; no name |

No call failed, and no answer carried the mock notice. Not seen in that run: a web result, an as-of
view, a failed call, a pin, the rate limit. One fault it found is fixed in the web panel: the fly-to
for the touching lot opened that lot as the page's site, which started a new conversation and
discarded the answer (that question was asked twice: the first answer was the one lost). The items
under "Not yet covered" below still stand.

**Which mode is running.** `GET /api/chat/setup` returns `"live": true` only when all three hold:
`FORESITE_CHAT_LIVE` is not `0`, a key is in the server's environment (`ANTHROPIC_API_KEY`), and the
`anthropic` package can be imported. Otherwise it returns `"live": false` and does not say which is
missing. To tell them apart on the server: read `FORESITE_CHAT_LIVE`, check the key variable is set
(without printing it), and run `python -c "import anthropic"`.

| What the reader sees | Meaning |
|---|---|
| "· offline answers" above the conversation | `/api/chat/setup` said `live: false`, or could not be reached |
| "Offline answer: no model was called", with the mock notice as the first line | A mock answer: `"offline": true` in the response |
| The same, with "The live model call did not complete, so this is a mock answer." first | The server is live, this call failed, and the answer is a mock |
| "Saved answer: the chat server could not be reached" | No server answered: an answer saved ahead of time, for the sample site only |
| None of these | A model answered: `"offline": false` |

**When a live call fails** the reader never sees an error. The server logs one warning,
`live chat call failed: ChatModelError: <reason>`, and answers in mock mode. The reason is the SDK's
error name (`AuthenticationError`, `BadRequestError`, `NotFoundError` for a model id the key cannot
use, `RateLimitError`, `APITimeoutError`, `APIConnectionError`), or one of: the model declined the
request; the answer ran past the token limit (8000); no answer was submitted within the request limit
(8 requests a question, each with a 120-second timeout and one retry). The fallback option is in beta:
after a 400 the code asks once more without it, and logs nothing.

**The quick first answer.** A full live answer takes 15 to 45 seconds, so with a live model the page
asks two things at once: `POST /api/chat` (the full answer) and `POST /api/chat/first`. The first route
makes one request to a fast model (`FORESITE_CHAT_FIRST_MODEL`, default `claude-haiku-5-5`, low effort,
20-second timeout) with the same instructions and site data, the answer tool forced, and no search of
any kind. What it proposes goes through the same checks as a full answer; a gap is dropped (a pass
that searched nothing cannot say "not found") and no page action is taken. The page shows it under the
line "A first answer, from this site's data alone…" with "Still working on the full answer…" below,
and the full answer replaces it. It is never sent back as history and never pinned.

The route answers with no parts whenever there is no first answer to show (no live model,
`FORESITE_CHAT_FIRST=0`, over 12 a minute, a failed or slow call, nothing that passed the checks), and
the page keeps waiting. It never refuses: why a question is refused is the full route's to say. A
failed first call logs `first chat answer failed: <reason>`. It costs a second, small model call for
each live question. When nothing it proposed passes the checks, it is sent back once with the reasons
(a second request); when something passes, that is shown at once. A first answer with nothing to show
logs `first chat answer had nothing to show: <reasons>`.

**What a live run of it has checked.** On 2026-11-14, two questions on screen for the sample site, a
local server with a key:

| Question | First answer | Full answer |
|---|---|---|
| What early warnings are there for this site? | 3.7 s: the server's count of rule results, under the first-answer notice | 25.8 s, replacing it |
| What happened next door? | 3.0 s: nothing to show, so the page kept "Looking this up" | 33.0 s |

So the fast model accepts the request (a strict tool, a forced tool call, low effort). Why the second
question had nothing to show is not known: that run logged no reason. The correction round and the
log line above were added after it and have not been run live.

**Not yet covered.** Worth doing before the demo leans on live answers:

- No test runs the stop reasons `refusal`, `max_tokens` or `pause_turn`, the retry after a 400, the
  reading of web search results off a response, or the limit of 12 live questions a minute. The tests
  use a scripted stand-in for the model, and one test runs the request loop against a fake SDK client.
- Token and search counts are counted for each live answer and then dropped: not logged, not returned.
  Read usage on the provider's console.
- A live answer is worth reading against the site routes once: every case, warning and action part has
  a `record_id` the matching route (`/similar`, `/warnings`, `/actions`) also returns; a `web` part's
  link is one the search returned; an as-of view has no web part and nothing dated on or after the day.
- `FORESITE_CHAT_LIVE=0` keeps a server with a key in mock mode. The key and any spend are the key
  holder's call.

## What it reads

One function, `(bbl, job_type, stage, as_of, project_id) -> SiteContext` (`chat_site_context.py`), passed to
`chat_router_for(...)` in `api/main.py`. That function is `app_context` (`chat_app_context.py`): it
reads the profile, similar cases, warnings and action items through `load_site_part` in
`sites_router.py`, the same function each site route answers from, and the layer list through
`load_layer_catalog`. So the chat and the page cannot disagree about what is on record, and an
owner's module that lands is picked up by the chat with no change here.

- A part that is still the labelled sample describes the sample site only. For any other lot it is
  "not available", and a question about it is answered "unknown": sample data is never shown as
  another site's. An answer resting on sample data carries the `X-ForeSite-Fixture` header.
- A part that fails to load is a failure with its reason, never an empty list.
- With no profile for the lot, the chat answers 404 rather than guess.
- **Early-warning rule checks** (`SiteContext.warning_checks`): when a rule could not run, "no warnings"
  is answered "unknown", a count of warnings is "at least", and warnings cited without a count carry a
  line saying not every rule could be confirmed as checked. `app_context` reads the checks from
  `early_warning.api.site_warning_checks`, the function behind `GET /api/sites/{bbl}/warnings/checks`, for
  the same lot and as-of day as the warnings, and only when the warnings themselves loaded. If that call
  fails, or answers off its contract, the checks are a failure with a reason: the chat then says it
  cannot tell whether every rule ran, with the same "unknown" and "at least" wording, and never
  assumes they all did. The rules run once for the warnings and once more for the checks.
- **The open project's checklist** (`SiteContext.project`, `chat_project_checklist.py`): when the request
  names a project and the project store holds it for this lot, the action items are that project's own
  items, read through the store: the list the project screen shows, with the owner and status its team
  set and any item a confirmed document added. The site facts are then read for the project's job type
  and stage, and the count sentence says "on the open project's checklist". Members' names are not
  read. With no project open, or one on another lot, or a view as of an earlier day, the items are the
  lot's general list and the chat is told it is not a project's checklist. A project that is open and
  cannot be read is a failure with its reason: the general list is shown with a line saying it is not
  the project's checklist.

Every piece that can fail to load is a `Loaded` with a status, because "could not load" must never
reach the chat as an empty list.

## Files

```
chat_models.py         request, sources, part kinds, page actions
chat_site_context.py   the seam: what the chat reads about a site
chat_site_view.py      the site on the as-of day; items a statement may cite; the model's reading text
chat_answer_build.py   proposed answer -> checked parts and actions; server-written counts and notices
chat_wording_checks.py the number check and the tone word lists
chat_record_search.py  search the records: the reader's part and the model's tool text
chat_case_search.py    search the past cases, the same way
chat_tools.py          the tools the model may call (search_records, search_similar_cases)
chat_prompt.py         the instructions and the tool the model answers through
chat_model_call.py     the model call with web search and our tools
chat_mock_answers.py   mock mode
chat_saved_answers_export.py  writes the web app's saved answers for the sample site
chat_service.py        live or mock: one answer
chat_contract_map.py   the chat's answer as the contract's ChatResponse; the contract's request as the chat's
chat_app_context.py    the site as the app's own site functions serve it (what the app mounts)
chat_project_checklist.py the open project's setup and checklist, read from the project store
chat_fixture_context.py the sample site from contracts/fixtures/ (the saved answers are built from it)
chat_router.py         POST /api/chat, GET /api/chat/setup, 12 live questions a minute
```

Tests: `python -m unittest discover -s tests -t .` (`tests/test_chat_core.py`, `tests/test_chat_service.py`,
`tests/test_chat_saved_answers.py`, `tests/test_chat_app_context.py`, `tests/test_chat_project_checklist.py`;
offline, a scripted model, no key).

Settings, all read from the server's environment: `ANTHROPIC_API_KEY` (the server only; never in the
repo or the web build), `FORESITE_CHAT_LIVE=0` to keep mock mode even with a key, `FORESITE_CHAT_MODEL`
(default `claude-opus-5-5`), `FORESITE_CHAT_EFFORT` (default `medium`).

## Limits

- No contract carries a site's list of records, so the record search and as-of counts answer "unknown"
  until one does. Dataset counts are the site profile's own.
- One source per part on the wire: a part resting on several records names them in `source_name` and
  links the first.
- The word-list checks catch plain phrasings and miss others. A person's name cannot be detected in code.
- The searches match words, not meaning.
- The chat reads the open project's checklist and setup, and nothing else of the project: not its notes,
  pins, documents or members. It changes nothing on the project except by pinning an answer.
- The web chat panel (`web/src/features/chat/`) and project panel (`web/src/features/project/`) sit in the
  app shell's chat slot, as two tabs.
