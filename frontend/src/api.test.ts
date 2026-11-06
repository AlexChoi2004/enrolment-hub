import { describe, expect, it, vi } from "vitest";
import { loadDashboard } from "./api";
import { fakeFetch, jsonResponse, raw } from "./test/helpers";

describe("loadDashboard", () => {
  it("returns the data when the server sends the agreed shape", async () => {
    const result = await loadDashboard("/api/dashboard", fakeFetch(jsonResponse(raw("sample"))));
    expect(result.status).toBe("ok");
    if (result.status === "ok") expect(result.data.period.label).toBe("Autumn 2027");
  });

  it("asks for JSON for this site only, and passes the abort signal on", async () => {
    const spy = vi.fn(async () => jsonResponse(raw("sample")));
    const controller = new AbortController();
    await loadDashboard("/api/dashboard", spy as unknown as typeof fetch, controller.signal);
    expect(spy).toHaveBeenCalledWith("/api/dashboard", { credentials: "same-origin", headers: { Accept: "application/json" }, signal: controller.signal });
  });

  it("sends no signal when there is none", async () => {
    const spy = vi.fn(async () => jsonResponse(raw("sample")));
    await loadDashboard("/api/dashboard", spy as unknown as typeof fetch);
    expect(spy).toHaveBeenCalledWith("/api/dashboard", { credentials: "same-origin", headers: { Accept: "application/json" } });
  });

  it("treats a redirect to the login page as an ended session", async () => {
    const result = await loadDashboard("/api/dashboard", fakeFetch(jsonResponse("<html>login</html>", { redirected: true, contentType: "text/html" })));
    expect(result).toEqual({ status: "error", message: "Your session has ended. Please log in again.", loginNeeded: true });
  });

  it("treats a reply that is not JSON as an ended session, even without a redirect flag", async () => {
    const result = await loadDashboard("/api/dashboard", fakeFetch(jsonResponse("<html></html>", { contentType: "text/html" })));
    expect(result).toMatchObject({ status: "error", loginNeeded: true });
  });

  it("reports a server error with its code", async () => {
    const result = await loadDashboard("/api/dashboard", fakeFetch(jsonResponse({ error: "boom" }, { status: 500 })));
    expect(result).toEqual({ status: "error", message: "The dashboard could not be loaded (error 500).", loginNeeded: false });
  });

  it("refuses data that is not in the agreed shape instead of showing it", async () => {
    const wrong = raw("sample") as Record<string, unknown>;
    delete wrong["graduation"];
    const result = await loadDashboard("/api/dashboard", fakeFetch(jsonResponse(wrong)));
    expect(result).toEqual({ status: "error", message: "The dashboard data was not in the expected shape.", loginNeeded: false });
  });

  it("refuses JSON that is not even an object", async () => {
    expect(await loadDashboard("/api/dashboard", fakeFetch(jsonResponse([1, 2, 3])))).toMatchObject({ status: "error" });
    expect(await loadDashboard("/api/dashboard", fakeFetch(jsonResponse("null")))).toMatchObject({ status: "error" });
  });

  it("turns a network failure into an error, never an exception", async () => {
    const result = await loadDashboard("/api/dashboard", fakeFetch(new TypeError("Failed to fetch")));
    expect(result).toEqual({ status: "error", message: "The dashboard could not be loaded. Check your connection and try again.", loginNeeded: false });
  });

  it("lets an abort through, because then the page is already gone", async () => {
    await expect(loadDashboard("/api/dashboard", fakeFetch(new DOMException("aborted", "AbortError")))).rejects.toThrow("aborted");
  });
});
