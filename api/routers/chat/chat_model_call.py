"""The live model call: Claude with Anthropic's server-side web search, answering through one strict tool.

The key stays on the server: it is read from the environment by the SDK, never logged, and never part
of a response. With no key or no SDK installed, `default_model()` returns None and the chat gives mock
answers (chat_mock_answers.py).
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from api.routers.chat.chat_answer_build import WebResult
from api.routers.chat.chat_models import ChatUsage
from api.routers.chat.chat_prompt import SUBMIT_TOOL, SUBMIT_TOOL_NAME
from api.routers.chat.chat_tools import MAX_TOOL_RUNS, ClientTool

MODEL = os.environ.get("FORESITE_CHAT_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("FORESITE_CHAT_EFFORT", "medium")
MAX_TOKENS = 8000
MAX_REQUESTS = 8  # per question: searches can pause a turn, tools take a round each, and one correction round is allowed
REQUEST_TIMEOUT_S = 120.0
# The quick first answer (chat_service.first_answer): a fast model, one request, no searches. Fallback
# models are not offered for this one, so none is asked for, and a forced tool call makes its reply the
# answer tool itself.
FIRST_MODEL = os.environ.get("FORESITE_CHAT_FIRST_MODEL", "claude-haiku-5-5")
FIRST_EFFORT = "low"
FIRST_MAX_TOKENS = 2000
FIRST_TIMEOUT_S = 20.0  # past this the full answer is close: the first one is no longer worth waiting for
# If a safety classifier declines a request, the API re-runs it on a fallback model in the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# The basic search tool: each search is called directly, so every result comes back as a block we can
# check a cited URL against. The two blocked sites forbid automated access in their terms
# (docs/api_data_sources.md).
WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 3,
    "blocked_domains": ["whoownswhat.justfix.org", "buildnyc.ai"],
    "user_location": {"type": "approximate", "city": "New York", "region": "New York", "country": "US",
                      "timezone": "America/New_York"},
}


class ChatModelError(Exception):
    """The live call gave nothing usable. The message is a short reason, safe to log."""


@dataclass
class ModelTurn:
    proposal: object  # the tool input, checked by chat_answer_build
    web_results: list[WebResult]
    searched: bool


@dataclass
class _Session:
    client: object
    model: str
    effort: str
    errors: tuple
    system: list
    messages: list
    tools: list
    usage: ChatUsage
    web_results: list[WebResult] = field(default_factory=list)
    searched: bool = False
    requests: int = 0
    pending: list[str] = field(default_factory=list)  # tool calls still owed a result
    client_tools: dict = field(default_factory=dict)  # name -> function run on this server (chat_tools)
    tool_runs: int = 0
    fallbacks: bool = True
    max_tokens: int = MAX_TOKENS
    max_requests: int = MAX_REQUESTS
    asks_again: bool = True  # a reply with no answer in it is sent back once more, within max_requests
    extra: dict = field(default_factory=dict)  # request options only this kind of call sends

    def turn(self, problems: Optional[list[str]] = None) -> ModelTurn:
        """One proposed answer. `problems` sends the last one back for a corrected list."""
        if problems:
            report = "The server held back parts of that answer:\n- " + "\n- ".join(problems) + \
                     f"\nCall {SUBMIT_TOOL_NAME} again with the full corrected list. Drop what cannot be sourced."
            self.messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": call, "is_error": True,
                 "content": report if number == 0 else "Only one call is read."}
                for number, call in enumerate(self.pending)]})
        while self.requests < self.max_requests:
            response = self._request()
            self.messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason == "refusal":
                raise ChatModelError("the model declined the request")
            if response.stop_reason == "max_tokens":
                raise ChatModelError("the answer ran past the token limit")
            if response.stop_reason == "pause_turn":
                continue  # a long search turn: sending it back unchanged resumes it
            calls = [b for b in response.content if b.type == "tool_use" and b.name == SUBMIT_TOOL_NAME]
            if calls:
                self.pending = [b.id for b in response.content if b.type == "tool_use"]
                return ModelTurn(proposal=calls[0].input, web_results=list(self.web_results), searched=self.searched)
            asked = [b for b in response.content if b.type == "tool_use" and b.name in self.client_tools]
            if asked:
                self.messages.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": call.id, "content": self._run(call)} for call in asked]})
                continue
            if not self.asks_again:
                break
            self.messages.append({"role": "user", "content": f"Nothing is shown until you call {SUBMIT_TOOL_NAME}. Call it now."})
        raise ChatModelError("no answer was submitted within the request limit")

    def _run(self, call) -> str:
        """One of our own tools. A failure is told to the model as nothing known; it never ends the question."""
        self.tool_runs += 1
        if self.tool_runs > MAX_TOOL_RUNS:
            return f"The tool limit for one question is reached. Call {SUBMIT_TOOL_NAME} with what you have."
        try:
            return self.client_tools[call.name](call.input if isinstance(call.input, dict) else {})
        except Exception:  # noqa: BLE001 - whatever went wrong, the model must not read it as an empty result
            return "The tool failed, so nothing is known from it. This is not an empty result."

    def _request(self):
        self.requests += 1
        request = dict(model=self.model, max_tokens=self.max_tokens, system=self.system, tools=self.tools,
                       messages=self.messages, output_config={"effort": self.effort}, **self.extra)
        try:
            try:
                response = self.client.beta.messages.create(
                    **request, **({"betas": [FALLBACK_BETA], "fallbacks": "default"} if self.fallbacks else {}))
            except self.errors as error:
                if not self.fallbacks or getattr(error, "status_code", None) != 400:
                    raise
                # The fallback option is in beta: if the API rejects the request, ask once more without it.
                self.fallbacks = False
                response = self.client.beta.messages.create(**request)
        except self.errors as error:
            raise ChatModelError(type(error).__name__) from error
        self._count(response)
        for block in response.content:
            if block.type == "server_tool_use" and block.name == "web_search":
                self.searched = True
            # A failed search carries one error object here instead of a list of results.
            if block.type == "web_search_tool_result" and isinstance(block.content, list):
                self.web_results += [WebResult(url=r.url, title=r.title, page_age=getattr(r, "page_age", None))
                                     for r in block.content if getattr(r, "type", "") == "web_search_result"]
        return response

    def _count(self, response) -> None:
        used = response.usage
        self.usage.model = response.model
        self.usage.input_tokens += (used.input_tokens + (getattr(used, "cache_read_input_tokens", 0) or 0)
                                    + (getattr(used, "cache_creation_input_tokens", 0) or 0))
        self.usage.output_tokens += used.output_tokens
        searches = getattr(used, "server_tool_use", None)
        self.usage.web_searches += (getattr(searches, "web_search_requests", 0) or 0) if searches else 0


class AnthropicChatModel:
    def __init__(self, client, model: str = MODEL, effort: str = EFFORT, errors: tuple = ()):
        self.client, self.model, self.effort, self.errors = client, model, effort, errors

    def open(self, system: list, messages: list, allow_web: bool, client_tools: tuple[ClientTool, ...] = ()) -> _Session:
        tools = ([WEB_SEARCH_TOOL] if allow_web else []) + [tool.schema for tool in client_tools] + [SUBMIT_TOOL]
        return _Session(client=self.client, model=self.model, effort=self.effort, errors=self.errors, system=system,
                        messages=list(messages), tools=tools, usage=ChatUsage(model=self.model),
                        client_tools={tool.schema["name"]: tool.run for tool in client_tools})

    def open_first(self, system: list, messages: list) -> _Session:
        """For the quick first answer: the fast model, with the answer tool and nothing else. One request,
        and at most one more when the server sends the answer back for correction."""
        return _Session(client=self.client, model=FIRST_MODEL, effort=FIRST_EFFORT, errors=self.errors, system=system,
                        messages=list(messages), tools=[SUBMIT_TOOL], usage=ChatUsage(model=FIRST_MODEL), fallbacks=False,
                        max_tokens=FIRST_MAX_TOKENS, max_requests=2, asks_again=False,
                        extra={"tool_choice": {"type": "tool", "name": SUBMIT_TOOL_NAME}, "timeout": FIRST_TIMEOUT_S})


def first_answers_on() -> bool:
    """FORESITE_CHAT_FIRST=0 switches the quick first answer off; the full answer is unchanged."""
    return os.environ.get("FORESITE_CHAT_FIRST", "1") != "0"


def default_model() -> Optional[AnthropicChatModel]:
    """None when live answers cannot run: switched off, no key in the environment, or no SDK installed."""
    if os.environ.get("FORESITE_CHAT_LIVE", "1") == "0":
        return None
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return None
    try:
        import anthropic
    except ImportError:
        return None
    client = anthropic.Anthropic(timeout=REQUEST_TIMEOUT_S, max_retries=1)
    return AnthropicChatModel(client, errors=(anthropic.APIStatusError, anthropic.APIConnectionError,
                                              anthropic.APITimeoutError))
