"""The chat's routes. `chat_router_for(load_context)` returns the router to mount in the app:
`POST /api/chat` (a question about one site), `POST /api/chat/first` (a quick first answer to the same
question, for the page to show while the full one is still at work) and `GET /api/chat/setup` (what a
client needs first).
"""

import time
from collections import deque
from typing import Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ValidationError

from api import contracts

from api.routers.chat import chat_model_call, chat_service
from api.routers.chat.chat_contract_map import from_contract, to_contract
from api.routers.chat.chat_models import MAX_EARLIER_EXCHANGES, MAX_HISTORY_CHARS, MAX_QUESTION_CHARS, ExampleQuestion
from api.routers.chat.chat_site_context import ContextLoader, SiteContext, SiteContextUnavailable

FIXTURE_HEADER = "X-ForeSite-Fixture"  # the same header api/stubs.py sets on sample data
# The key is the team's: one process answers at most this many live questions a minute.
LIVE_QUESTIONS_PER_MINUTE = 12


class ChatSetup(BaseModel):
    """What a client needs before the first question."""

    live: bool
    examples: list[ExampleQuestion] = []
    max_question_chars: int = MAX_QUESTION_CHARS
    max_earlier_exchanges: int = MAX_EARLIER_EXCHANGES
    max_history_chars: int = MAX_HISTORY_CHARS


def chat_router_for(load_context: ContextLoader) -> APIRouter:
    """An answer that rests on sample data carries the fixture header, as every other route's does."""
    router = APIRouter(prefix="/api/chat", tags=["chat"])
    recent_live: deque = deque()
    recent_first: deque = deque()  # counted apart, so a first answer never uses up a question's slot

    def slot_in(recent: deque, now: float) -> bool:
        while recent and now - recent[0] > 60:
            recent.popleft()
        if len(recent) >= LIVE_QUESTIONS_PER_MINUTE:
            return False
        recent.append(now)
        return True

    def marking(response: Response) -> ContextLoader:
        def load(*site: Optional[str]) -> SiteContext:
            context = load_context(*site)
            if context.sample:
                response.headers[FIXTURE_HEADER] = "true"
            return context
        return load

    @router.get("/setup", response_model=ChatSetup)
    def chat_setup() -> ChatSetup:
        return ChatSetup(live=chat_model_call.default_model() is not None)

    @router.post("", response_model=contracts.ChatResponse)
    def chat_answer(body: contracts.ChatRequest, response: Response) -> contracts.ChatResponse:
        """A question about one site, answered in parts that each say where they came from."""
        if not body.bbl:
            return contracts.ChatResponse(offline=True, actions=[], answer_parts=[contracts.ChatAnswerPart(
                kind="notice", text="Pick a site on the map first: the chat answers about one site at a time.")])
        try:
            request = from_contract(body)
        except ValidationError as error:
            raise HTTPException(status_code=422, detail=[e["msg"] for e in error.errors()])
        model = chat_model_call.default_model()
        if model is not None and not slot_in(recent_live, time.monotonic()):
            raise HTTPException(status_code=429, detail="Too many live questions this minute. Wait a moment and ask again.")
        try:
            return to_contract(chat_service.answer(request, marking(response), model))
        except SiteContextUnavailable:
            raise HTTPException(status_code=404, detail="No data could be loaded for that site.")

    @router.post("/first", response_model=contracts.ChatResponse)
    def chat_first_answer(body: contracts.ChatRequest, response: Response) -> contracts.ChatResponse:
        """A quick first answer from the site's data alone, to show while POST /api/chat is still at work.

        No parts means there is none to show (no live model, switched off, over the limit, a failed call,
        or nothing that passed the checks): the page keeps waiting. Why a question is refused is the full
        route's to say, so this one never refuses.
        """
        nothing = contracts.ChatResponse(answer_parts=[], actions=[], offline=False)
        model = chat_model_call.default_model()
        if model is None or not body.bbl or not chat_model_call.first_answers_on():
            return nothing
        try:
            request = from_contract(body)
        except ValidationError:
            return nothing
        if not slot_in(recent_first, time.monotonic()):
            return nothing
        try:
            answer = chat_service.first_answer(request, marking(response), model)
        except SiteContextUnavailable:
            return nothing
        return to_contract(answer) if answer else nothing

    return router
