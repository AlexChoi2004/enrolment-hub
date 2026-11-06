import { describe, expect, it, vi } from "vitest";
import { loadBoard, moveCard } from "./api";
import { fakeFetch, jsonResponse, boardRaw, moveRaw } from "../test/helpers";

describe("loadBoard", () => {
  it("returns the board in the agreed shape", async () => {
    const result = await loadBoard("/api/planner/board", fakeFetch(jsonResponse(boardRaw("failed"))));
    expect(result.status).toBe("ok");
    if (result.status === "ok") expect(result.board.columns).toHaveLength(10);
  });
  it("treats a redirect to the login page, or a non-JSON reply, as an ended session", async () => {
    expect(await loadBoard("/x", fakeFetch(jsonResponse("<html></html>", { redirected: true, contentType: "text/html" })))).toMatchObject({ status: "error", loginNeeded: true });
    expect(await loadBoard("/x", fakeFetch(jsonResponse("<html></html>", { contentType: "text/html" })))).toMatchObject({ loginNeeded: true });
  });
  it("reports a server error, a wrong shape and a network failure as messages", async () => {
    expect(await loadBoard("/x", fakeFetch(jsonResponse({}, { status: 500 })))).toMatchObject({ message: "The board could not be loaded (error 500).", loginNeeded: false });
    expect(await loadBoard("/x", fakeFetch(jsonResponse({ nope: 1 })))).toMatchObject({ message: "The board data was not in the expected shape." });
    expect(await loadBoard("/x", fakeFetch(new TypeError("offline")))).toMatchObject({ message: expect.stringContaining("Check your connection") });
  });
  it("lets an abort through", async () => {
    await expect(loadBoard("/x", fakeFetch(new DOMException("aborted", "AbortError")))).rejects.toThrow("aborted");
  });
});

describe("moveCard", () => {
  const call = (response: Response | Error) => moveCard("/api/planner/move", "token-123", "48024", "Spring 2027", fakeFetch(response));

  it("sends JSON with the CSRF token, to this site only", async () => {
    const spy = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => jsonResponse(moveRaw("ok")));
    await moveCard("/api/planner/move", "token-123", "48024", "Spring 2027", spy as unknown as typeof fetch);
    expect(spy).toHaveBeenCalledWith("/api/planner/move", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": "token-123" },
      body: JSON.stringify({ code: "48024", to: "Spring 2027" }),
    });
  });
  it("asks to take a subject out of the plan with a null session", async () => {
    const spy = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => jsonResponse(moveRaw("ok")));
    await moveCard("/m", "t", "48024", null, spy as unknown as typeof fetch);
    expect(JSON.parse(String(spy.mock.calls[0]?.[1]?.body))).toEqual({ code: "48024", to: null });
  });
  it("returns the message and the board as the server now has it", async () => {
    const result = await call(jsonResponse(moveRaw("ok")));
    expect(result.status).toBe("moved");
    if (result.status === "moved") {
      expect(result.message).toBe("Added 48024 Programming 2 to your plan for Spring 2027.");
      expect(result.board.columns.find((c) => c.label === "Spring 2027")?.cards.some((c) => c.code === "48024")).toBe(true);
    }
  });
  it("shows the planner's own reason when it refuses", async () => {
    const result = await call(jsonResponse(moveRaw("refused"), { status: 422 }));
    expect(result).toEqual({ status: "refused", message: expect.stringContaining("31251 Data Structures and Algorithms is planned for Spring 2027") });
  });
  it("treats a bad request as an error, not a refusal", async () => {
    expect(await call(jsonResponse(moveRaw("bad"), { status: 400 }))).toEqual({ status: "error", message: "That is not a session, for example Autumn 2028.", loginNeeded: false });
  });
  it("treats an ended session, a wrong shape and a network failure as errors", async () => {
    expect(await call(jsonResponse("<html></html>", { redirected: true, contentType: "text/html" }))).toMatchObject({ status: "error", loginNeeded: true });
    expect(await call(jsonResponse({ ok: true }))).toMatchObject({ status: "error", message: "The server's answer was not in the expected shape." });
    expect(await call(new TypeError("offline"))).toMatchObject({ status: "error", loginNeeded: false, message: expect.stringContaining("could not be sent") });
  });
  it("never throws", async () => {
    await expect(call(new Error("anything"))).resolves.toMatchObject({ status: "error" });
  });
});
