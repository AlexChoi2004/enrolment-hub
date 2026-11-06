import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { fakeFetch, jsonResponse, raw } from "./test/helpers";

describe("App", () => {
  it("shows a loading message, then the dashboard", async () => {
    render(<App endpoint="/api/dashboard" fetchImpl={fakeFetch(jsonResponse(raw("sample")))} />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading your dashboard…");
    expect(await screen.findByRole("heading", { name: "Welcome back, John" })).toBeInTheDocument();
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("asks the endpoint it was given", async () => {
    const spy = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => jsonResponse(raw("fresh")));
    render(<App endpoint="/api/dashboard" fetchImpl={spy as unknown as typeof fetch} />);
    await screen.findByRole("heading", { name: "Welcome back, John" });
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy.mock.calls[0]?.[0]).toBe("/api/dashboard");
  });

  it("shows an error, with a way back to the login page, when the session has ended", async () => {
    render(<App endpoint="/api/dashboard" fetchImpl={fakeFetch(jsonResponse("<html></html>", { redirected: true, contentType: "text/html" }))} />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Your session has ended. Please log in again.");
    expect(screen.getByRole("link", { name: "Go to the login page" })).toHaveAttribute("href", "/login");
  });

  it("shows an error with no login link for other failures", async () => {
    render(<App endpoint="/api/dashboard" fetchImpl={fakeFetch(jsonResponse({}, { status: 500 }))} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("error 500");
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("shows an error instead of crashing when the data is in the wrong shape", async () => {
    render(<App endpoint="/api/dashboard" fetchImpl={fakeFetch(jsonResponse({ unexpected: true }))} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("not in the expected shape");
  });

  it("shows an error when the network fails", async () => {
    render(<App endpoint="/api/dashboard" fetchImpl={fakeFetch(new TypeError("offline"))} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Check your connection");
  });

  it("does not update after it has been removed from the page", async () => {
    let release: (r: Response) => void = () => undefined;
    const slow = fakeFetch(() => new Promise<Response>((resolve) => (release = resolve)));
    const errors = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const view = render(<App endpoint="/api/dashboard" fetchImpl={slow} />);
    view.unmount();
    release(jsonResponse(raw("sample")));
    await waitFor(() => expect(errors).not.toHaveBeenCalled());
    errors.mockRestore();
  });
});
