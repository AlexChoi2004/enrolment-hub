import { type Dashboard, parseDashboard } from "../contract";

const files = import.meta.glob("./fixtures/*.json", { eager: true, import: "default" }) as Record<string, unknown>;

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
