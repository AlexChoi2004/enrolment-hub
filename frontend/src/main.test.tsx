import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { mount } from "./main";
import { fakeFetch, jsonResponse, raw } from "./test/helpers";

describe("mount", () => {
  it("renders the dashboard into the element the Flask page provides, using its data-endpoint", async () => {
    const root = document.createElement("div");
    root.dataset["endpoint"] = "/api/dashboard";
    document.body.appendChild(root);
    const spy = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => jsonResponse(raw("sample")));
    mount(root, spy as unknown as typeof fetch);
    expect(await screen.findByRole("heading", { name: "Welcome back, John" })).toBeInTheDocument();
    expect(spy.mock.calls[0]?.[0]).toBe("/api/dashboard");
    root.remove();
  });

  it("does nothing on a page without the element or without an endpoint", () => {
    const noEndpoint = document.createElement("div");
    expect(() => mount(null)).not.toThrow();
    expect(() => mount(noEndpoint, fakeFetch(jsonResponse(raw("sample"))))).not.toThrow();
    expect(noEndpoint.innerHTML).toBe("");
  });
});
