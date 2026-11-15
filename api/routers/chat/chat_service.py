"""One question in, one typed answer out.

The chat reads the site through one loader (chat_site_context), the same data the page shows, so the
chat and the screen cannot disagree about what is on record.
"""

import logging
import re
from typing import Optional

from api.routers.chat import chat_mock_answers, chat_tools
from api.routers.chat.chat_answer_build import Built, build_parts, notice, plain_text, without_repeats
from api.routers.chat.chat_models import AnswerPart, ChatAnswer, ChatRequest, ChatUsage, PageAction
from api.routers.chat.chat_prompt import conversation, first_pass_blocks, system_blocks
from api.routers.chat.chat_site_context import ContextLoader
from api.routers.chat.chat_site_view import SiteView

log = logging.getLogger("foresite.chat")

# A question that asks for a verdict, a forecast or a name gets the matching notice whatever the model does.
_ASKS_VERDICT = re.compile(r"\b(?:safe|unsafe|safely|compliant|comply|complies|compliance|legal|illegal|fault|blame|"
                           r"negligen\w*|liable)\b", re.I)
_ASKS_FORECAST = re.compile(r"\bwill (?:it|this|the)\b|\bgoing to (?:collapse|fail|fall)\b|\bhow likely\b|\bpredict\w*|"
                            r"\bchances?\b|\bprobab\w+", re.I)
_ASKS_NAME = re.compile(r"\b(?:owner|contractor|applicant|engineer|architect|developer|landlord)'?s?\s+name\b|\bname of\b", re.I)
_ASKS_WHO = re.compile(r"\bwho\b", re.I)
# "Who owns that item?" about the open project's checklist asks for a role, which the chat gives: no names notice.
_ABOUT_CHECKLIST = re.compile(r"\bchecklist\b|\b(?:action )?items?\b|\btasks?\b", re.I)


def answer(request: ChatRequest, load_context: ContextLoader, model=None) -> ChatAnswer:
    """`model` is a chat_model_call.AnthropicChatModel, or None when live answers cannot run: the
    question then gets a mock answer (chat_mock_answers), labeled as one.

    Raises chat_site_context.SiteContextUnavailable for a site no context can be built for, and
    LookupError for a saved example (none are written yet).
    """
    as_of = request.as_of.isoformat() if request.as_of else None
    view = SiteView(load_context(request.bbl, request.job_type, request.stage, as_of, request.project_id))
    if request.example_id:
        raise LookupError(f"no saved example {request.example_id!r} for lot {request.bbl}")
    if model is None:
        return _mock(request, view, [])
    try:
        return _live(request, view, model)
    except Exception as error:  # the demo must not crash on a failed call; the reason is logged, never shown
        log.warning("live chat call failed: %s: %s", type(error).__name__, error)
        return _mock(request, view, [notice("live_failed")])


def first_answer(request: ChatRequest, load_context: ContextLoader, model=None) -> Optional[ChatAnswer]:
    """A short first answer from the site data alone, for the page to show while `answer` is still at work.

    None whenever there is nothing worth showing: no live model, a failed or slow call, or an answer the
    checks left with no sourced part (the reason is logged). It goes through the same checks as a full
    answer, takes no page action, and drops a gap: "not found" from a pass that searched nothing would
    be false. Raises chat_site_context.SiteContextUnavailable as `answer` does.
    """
    if model is None or request.example_id:
        return None
    as_of = request.as_of.isoformat() if request.as_of else None
    view = SiteView(load_context(request.bbl, request.job_type, request.stage, as_of, request.project_id))
    question = request.question.strip()
    try:
        session = model.open_first(first_pass_blocks(view), conversation(request.history, question))
        built = _first_built(view, session.turn().proposal)
        if built.problems and not _has_sourced_part(built):  # one correction round, only when nothing got through
            built = _first_built(view, session.turn(built.problems).proposal)
    except Exception as error:  # the full answer is on its way: a failed first pass is only logged
        log.warning("first chat answer failed: %s: %s", type(error).__name__, error)
        return None
    if not _has_sourced_part(built):
        log.warning("first chat answer had nothing to show: %s", built.problems or "it gave only a gap or a notice")
        return None
    parts = [notice("first_pass")] + _question_notices(question, view) + built.parts
    return _finish(request, view, "live", parts, [], "off_as_of" if view.as_of else "not_used", session.usage)


def _first_built(view: SiteView, proposal: object) -> Built:
    """The first pass's proposal through the checks, without its gaps and its actions."""
    items = proposal.get("items") if isinstance(proposal, dict) else None
    kept = [item for item in items if not (isinstance(item, dict) and item.get("kind") == "gap")] if isinstance(items, list) else []
    return build_parts(view, {"items": kept, "actions": []}, []) if kept else Built()


def _has_sourced_part(built: Built) -> bool:
    return any(part.kind != "notice" for part in built.parts)


def _live(request: ChatRequest, view: SiteView, model) -> ChatAnswer:
    question = request.question.strip()
    session = model.open(system_blocks(view), conversation(request.history, question), allow_web=view.as_of is None,
                         client_tools=tuple(chat_tools.tools_for(view)))
    turn = session.turn()
    pin = (request.project_id, bool(request.history))
    built = build_parts(view, turn.proposal, turn.web_results, turn.searched, *pin)
    if built.problems:  # one correction round, with the reasons
        turn = session.turn(built.problems)
        built = build_parts(view, turn.proposal, turn.web_results, turn.searched, *pin)
    parts = _question_notices(question, view) + built.parts + _problem_notices(built)
    if built.problems:
        log.info("chat held back %d item(s): %s", len(built.problems), built.problems)
    if all(part.kind == "notice" for part in built.parts) and not built.actions:
        parts.append(notice("no_answer"))
    if view.as_of:
        parts.append(notice("web_off_as_of"))
    web = "off_as_of" if view.as_of else ("used" if turn.searched else "not_used")
    return _finish(request, view, "live", parts, built.actions, web, session.usage)


def _question_notices(question: str, view: Optional[SiteView] = None) -> list[AnswerPart]:
    parts: list[AnswerPart] = []
    if _ASKS_VERDICT.search(question):
        parts.append(notice("not_a_determination"))
    if _ASKS_FORECAST.search(question):
        parts.append(notice("not_a_prediction"))
    about_a_role = view is not None and view.project_open and _ABOUT_CHECKLIST.search(question)
    if _ASKS_NAME.search(question) or (_ASKS_WHO.search(question) and not about_a_role):
        parts.append(notice("names_withheld"))
    return parts


def _problem_notices(built: Built) -> list[AnswerPart]:
    parts: list[AnswerPart] = []
    if len(built.problems) > built.actions_dropped + built.after_as_of:
        parts.append(notice("held_back"))
    if built.after_as_of:
        parts.append(notice("after_as_of"))
    if built.actions_dropped:
        parts.append(notice("action_dropped"))
    return parts


def _mock(request: ChatRequest, view: SiteView, first: list[AnswerPart]) -> ChatAnswer:
    """No model: a prepared answer matched by keyword, through the same checks as a live one."""
    question = request.question.strip()
    parts = first + [notice("mock_answer")] + _question_notices(question, view)
    proposed = chat_mock_answers.propose(view, question)
    if not proposed:
        return _finish(request, view, "mock", parts + [notice("mock_no_match")], [], "off")
    built = build_parts(view, proposed, [], project_id=request.project_id, has_history=bool(request.history))
    if built.problems:
        log.warning("mock answer for lot %s out of step with the site data: %s", request.bbl, built.problems)
    return _finish(request, view, "mock", parts + built.parts + _problem_notices(built), built.actions, "off")


def _finish(request: ChatRequest, view: SiteView, mode: str, parts: list[AnswerPart], actions: list[PageAction],
            web: str, usage: Optional[ChatUsage] = None) -> ChatAnswer:
    parts = without_repeats(parts)
    return ChatAnswer(mode=mode, question=request.question.strip(), parts=parts, actions=actions,
                      plain_text=plain_text(parts), as_of=view.as_of, web_search=web, usage=usage)
