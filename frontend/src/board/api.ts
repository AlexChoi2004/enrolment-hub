import { type Board, BoardSchema, MoveResponseSchema } from "./contract";

export type BoardLoaded = { status: "ok"; board: Board } | { status: "error"; message: string; loginNeeded: boolean };
export type MoveOutcome =
  | { status: "moved"; message: string; board: Board }
  | { status: "refused"; message: string }
  | { status: "error"; message: string; loginNeeded: boolean };

const SESSION_ENDED = "Your session has ended. Please log in again.";
const isJson = (response: Response) => (response.headers.get("content-type") ?? "").includes("application/json");

/** Load the board. Never throws (except an abort, because then the page is gone): every failure becomes a message to show. */
export async function loadBoard(endpoint: string, fetchImpl: typeof fetch = fetch, signal?: AbortSignal): Promise<BoardLoaded> {
  try {
    const response = await fetchImpl(endpoint, { credentials: "same-origin", headers: { Accept: "application/json" }, ...(signal ? { signal } : {}) });
    if (response.redirected || !isJson(response)) return { status: "error", message: SESSION_ENDED, loginNeeded: true };
    if (!response.ok) return { status: "error", message: `The board could not be loaded (error ${response.status}).`, loginNeeded: false };
    const parsed = BoardSchema.safeParse(await response.json());
    if (!parsed.success) return { status: "error", message: "The board data was not in the expected shape.", loginNeeded: false };
    return { status: "ok", board: parsed.data };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    return { status: "error", message: "The board could not be loaded. Check your connection and try again.", loginNeeded: false };
  }
}

/**
 * Ask the server to place a subject in a session (to = a label), or take it out of the plan (to = null).
 * "refused" means the planner said no and gave its reason; nothing changed. "moved" carries the board as the server now has it.
 */
export async function moveCard(
  endpoint: string, csrf: string, code: string, to: string | null, fetchImpl: typeof fetch = fetch,
): Promise<MoveOutcome> {
  try {
    const response = await fetchImpl(endpoint, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": csrf },
      body: JSON.stringify({ code, to }),
    });
    if (response.redirected || !isJson(response)) return { status: "error", message: SESSION_ENDED, loginNeeded: true };
    const parsed = MoveResponseSchema.safeParse(await response.json());
    if (!parsed.success) return { status: "error", message: "The server's answer was not in the expected shape.", loginNeeded: false };
    if (parsed.data.ok) return { status: "moved", message: parsed.data.message, board: parsed.data.board };
    return response.status === 422
      ? { status: "refused", message: parsed.data.error }
      : { status: "error", message: parsed.data.error, loginNeeded: false };
  } catch {
    return { status: "error", message: "The move could not be sent. Check your connection and try again.", loginNeeded: false };
  }
}
