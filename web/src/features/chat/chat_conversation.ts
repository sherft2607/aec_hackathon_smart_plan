// The conversation the panel keeps: each question and what came back for it.
import type { ChatRequest, ChatResponse } from "../../contracts";
import type { ChatSetup } from "./chat_client";
import { answerText } from "./chat_part_kinds";

export type Exchange = {
  id: number;
  question: string;
  outcome:
    // `first` is the server's quick first answer, shown until the full one replaces it. It is never
    // sent back as history and never pinned: only an answered exchange is.
    | { state: "waiting"; first?: { response: ChatResponse; sample: boolean } }
    | { state: "answered"; response: ChatResponse; sample: boolean; saved: boolean; notDone: string[] }
    | { state: "refused"; reason: string }
    | { state: "unreachable" };
};

export type AnsweredExchange = Exchange & { outcome: { state: "answered" } };

export const isAnswered = (exchange: Exchange): exchange is AnsweredExchange => exchange.outcome.state === "answered";

/**
 * The earlier questions and answers a follow-up sends, within the server's caps. The server refuses a
 * request over a cap rather than cutting it, so the oldest exchanges are left out here, whole.
 */
export function historyFor(exchanges: Exchange[], setup: ChatSetup): NonNullable<ChatRequest["history"]> {
  const perAnswerCap = 4000;
  const kept: NonNullable<ChatRequest["history"]> = [];
  let size = 0;
  for (const exchange of exchanges.filter(isAnswered).reverse()) {
    const answer = answerText(exchange.outcome.response.answer_parts);
    if (answer.length > perAnswerCap || exchange.question.length > setup.max_question_chars) continue;
    size += exchange.question.length + answer.length;
    if (kept.length >= setup.max_earlier_exchanges || size > setup.max_history_chars) break;
    kept.unshift({ question: exchange.question, answer });
  }
  return kept;
}
