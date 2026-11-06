import { type Dashboard, DashboardSchema } from "./contract";

export type Loaded = { status: "ok"; data: Dashboard } | { status: "error"; message: string; loginNeeded: boolean };

/**
 * Load the dashboard. It never throws: every way it can go wrong becomes an error the page can show.
 * The server answers an expired session with a redirect to the login page, which fetch follows, so a reply that is
 * not JSON is treated as "please log in again".
 */
export async function loadDashboard(endpoint: string, fetchImpl: typeof fetch = fetch, signal?: AbortSignal): Promise<Loaded> {
  try {
    const response = await fetchImpl(endpoint, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
      ...(signal ? { signal } : {}),
    });
    const isJson = (response.headers.get("content-type") ?? "").includes("application/json");
    if (response.redirected || !isJson) return { status: "error", message: "Your session has ended. Please log in again.", loginNeeded: true };
    if (!response.ok) return { status: "error", message: `The dashboard could not be loaded (error ${response.status}).`, loginNeeded: false };
    const parsed = DashboardSchema.safeParse(await response.json());
    if (!parsed.success) return { status: "error", message: "The dashboard data was not in the expected shape.", loginNeeded: false };
    return { status: "ok", data: parsed.data };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error; // the page went away: nothing to show
    return { status: "error", message: "The dashboard could not be loaded. Check your connection and try again.", loginNeeded: false };
  }
}
