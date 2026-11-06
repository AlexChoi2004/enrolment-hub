import { describe, expect, it } from "vitest";
import { DashboardSchema, STEP_KINDS, WORKLOADS, parseDashboard } from "./contract";
import { allFixtures, fixtureCount, raw } from "./test/helpers";

describe("what the server really sends", () => {
  it("has a fixture for each of the four demo starting points", () => {
    expect(fixtureCount).toBe(4);
  });

  it.each(allFixtures)("%s matches the contract", (_name, json) => {
    expect(() => parseDashboard(json)).not.toThrow();
  });
});

describe("the contract is strict, so the two sides cannot drift apart quietly", () => {
  const mutate = (change: (d: Record<string, any>) => void) => {
    const data = raw("sample") as Record<string, any>;
    change(data);
    return DashboardSchema.safeParse(data);
  };

  it("accepts the unchanged sample", () => {
    expect(mutate(() => undefined).success).toBe(true);
  });

  it("rejects a missing key", () => {
    expect(mutate((d) => delete d.degree.total_cp).success).toBe(false);
    expect(mutate((d) => delete d.graduation).success).toBe(false);
  });

  it("rejects a key the server has added", () => {
    expect(mutate((d) => (d.hacked = true)).success).toBe(false);
    expect(mutate((d) => (d.degree.surprise = 1)).success).toBe(false);
  });

  it("rejects the wrong type, negative numbers and fractions", () => {
    expect(mutate((d) => (d.degree.completed_cp = "96")).success).toBe(false);
    expect(mutate((d) => (d.degree.completed_cp = -1)).success).toBe(false);
    expect(mutate((d) => (d.period.year = 2.5)).success).toBe(false);
  });

  it("rejects a workload or a step kind it does not know", () => {
    expect(mutate((d) => (d.sessions[0].workload = "extreme")).success).toBe(false);
    expect(mutate((d) => (d.next_steps[0].kind = "hack")).success).toBe(false);
  });

  it("allows an unknown workload only as null (not enough information)", () => {
    expect(mutate((d) => (d.sessions[0].workload = null)).success).toBe(true);
  });

  it("only allows links that stay on this site", () => {
    for (const href of ["https://evil.example", "//evil.example", "javascript:alert(1)", ""]) {
      expect(mutate((d) => (d.next_steps[0].href = href)).success, href).toBe(false);
    }
  });

  it("lists the same workloads and step kinds the server can send", () => {
    expect([...WORKLOADS]).toEqual(["light", "balanced", "heavy", "too_heavy"]);
    expect([...STEP_KINDS]).toEqual(["setup", "retake", "blocked", "reschedule", "workload", "enrol", "plan"]);
  });

  it("throws a readable error from parseDashboard", () => {
    expect(() => parseDashboard({})).toThrow();
    expect(() => parseDashboard(null)).toThrow();
    expect(() => parseDashboard("text")).toThrow();
  });
});

describe("same-site links", () => {
  it("accepts ordinary paths and rejects anything a browser could read as another site", async () => {
    const { SAME_SITE_PATH } = await import("./contract");
    for (const ok of ["/planner", "/major", "/subjects?x=1", "/a/b"]) expect(SAME_SITE_PATH.test(ok), ok).toBe(true);
    for (const bad of ["//evil.example", "/\\evil.example", "https://evil.example", "javascript:alert(1)", "planner", "", " /planner"]) {
      expect(SAME_SITE_PATH.test(bad), bad).toBe(false);
    }
  });
});
