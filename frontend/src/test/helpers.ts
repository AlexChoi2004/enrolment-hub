import { type Dashboard, parseDashboard } from "../contract";

const files = import.meta.glob("./fixtures/dashboard.*.json", { eager: true, import: "default" }) as Record<string, unknown>;
const boardFiles = import.meta.glob("./fixtures/board.*.json", { eager: true, import: "default" }) as Record<string, unknown>;
const moveFiles = import.meta.glob("./fixtures/move.*.json", { eager: true, import: "default" }) as Record<string, unknown>;

export type Preset = "fresh" | "sample" | "late" | "failed";

/** The data the real server produced for one demo starting point (see tests/features/dashboard/test_contract.py). */
export function raw(name: Preset): unknown {
  return structuredClone(files[`./fixtures/dashboard.${name}.json`]);
}

export function fixture(name: Preset): Dashboard {
  return parseDashboard(raw(name));
}

export const fixtureCount = Object.keys(files).length;
export const allFixtures = Object.entries(files);

export function jsonResponse(body: unknown, options: { status?: number; redirected?: boolean; contentType?: string } = {}): Response {
  const response = new Response(typeof body === "string" ? body : JSON.stringify(body), {
    status: options.status ?? 200,
    headers: { "Content-Type": options.contentType ?? "application/json" },
  });
  if (options.redirected) Object.defineProperty(response, "redirected", { value: true });
  return response;
}

export function fakeFetch(response: Response | (() => Promise<Response>) | Error | DOMException): typeof fetch {
  return (async () => {
    if (response instanceof Error || response instanceof DOMException) throw response;
    return typeof response === "function" ? response() : response.clone();
  }) as typeof fetch;
}

/** The planner board as the real server sent it for one starting point. */
export function boardRaw(name: Preset): unknown {
  return structuredClone(boardFiles[`./fixtures/board.${name}.json`]);
}
export const allBoardFixtures = Object.entries(boardFiles);

/** The server's real answers to a move: it worked, the planner refused with a reason, or the request was bad. */
export function moveRaw(name: "ok" | "refused" | "bad"): unknown {
  return structuredClone(moveFiles[`./fixtures/move.${name}.json`]);
}
