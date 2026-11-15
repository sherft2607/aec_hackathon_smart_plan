// The chat's own calls to the API. The shared client (web/src/api/client.ts) answers with a fixture when
// the API is down, which suits a panel of data but not a chat: a fixed answer shown under a question it
// was not written for would read as the answer. So this tells "the server answered" apart from "the
// server refused, and said why" and "no server".
import { API_BASE, STATIC } from "../../api/client";
import type { ChatRequest, ChatResponse } from "../../contracts";

export type ChatSetup = {
  live: boolean;
  max_question_chars: number;
  max_earlier_exchanges: number;
  max_history_chars: number;
};

// The server's own caps, used until /api/chat/setup answers.
export const DEFAULT_CHAT_SETUP: ChatSetup = {
  live: false,
  max_question_chars: 1000,
  max_earlier_exchanges: 8,
  max_history_chars: 12000,
};

export type ChatResult =
  | { status: "answered"; response: ChatResponse; sample: boolean }
  | { status: "refused"; reason: string }
  | { status: "unreachable" };

const FIXTURE_HEADER = "X-ForeSite-Fixture";

function reasonFrom(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (!Array.isArray(detail)) return null;
  const lines = detail
    .map((item) => (typeof item === "string" ? item : typeof item?.msg === "string" ? item.msg : null))
    .filter((line): line is string => line !== null);
  return lines.length ? lines.join("; ") : null;
}

export async function askChat(body: ChatRequest, signal?: AbortSignal): Promise<ChatResult> {
  if (STATIC) return { status: "unreachable" };
  try {
    const response = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
    const payload: unknown = await response.json();
    if (response.ok) {
      const answer = payload as ChatResponse;
      if (!Array.isArray(answer?.answer_parts) || !Array.isArray(answer?.actions)) return { status: "unreachable" };
      return { status: "answered", response: answer, sample: response.headers.get(FIXTURE_HEADER) === "true" };
    }
    // A refusal the server explains (over a cap, too many questions, no data for the site).
    const reason = response.status < 500 ? reasonFrom((payload as { detail?: unknown })?.detail) : null;
    return reason ? { status: "refused", reason } : { status: "unreachable" };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    return { status: "unreachable" }; // no server, or an answer that is not the API's (a proxy or host page)
  }
}

/**
 * The quick first answer to the same question, to show while `askChat` is still waiting. Null whenever
 * there is none to show: the server had none, refused, or could not be reached. It is never an error to
 * the reader, because the full answer is still on its way.
 */
export async function askChatFirst(body: ChatRequest, signal?: AbortSignal): Promise<{ response: ChatResponse; sample: boolean } | null> {
  if (STATIC) return null;
  try {
    const response = await fetch(`${API_BASE}/api/chat/first`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
    if (!response.ok) return null;
    const answer = (await response.json()) as ChatResponse;
    if (!Array.isArray(answer?.answer_parts) || answer.answer_parts.length === 0) return null;
    return { response: answer, sample: response.headers.get(FIXTURE_HEADER) === "true" };
  } catch {
    return null;
  }
}

export async function loadChatSetup(signal?: AbortSignal): Promise<ChatSetup | null> {
  if (STATIC) return null;
  try {
    const response = await fetch(`${API_BASE}/api/chat/setup`, { signal });
    if (!response.ok) return null;
    const setup = (await response.json()) as Partial<ChatSetup>;
    return typeof setup.live === "boolean" ? { ...DEFAULT_CHAT_SETUP, ...setup } : null;
  } catch {
    return null;
  }
}
