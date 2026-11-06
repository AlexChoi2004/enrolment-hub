import { describe, expect, it } from "vitest";
import { EDGE_ZONE, MAX_STEP, edgeDelta } from "./scroll";

describe("edgeDelta", () => {
  it("does nothing in the middle of an area", () => {
    expect(edgeDelta(500, 0, 1000)).toBe(0);
    expect(edgeDelta(EDGE_ZONE, 0, 1000)).toBe(0);
    expect(edgeDelta(1000 - EDGE_ZONE, 0, 1000)).toBe(0);
  });

  it("scrolls towards the start near the start, and towards the end near the end", () => {
    expect(edgeDelta(10, 0, 1000)).toBeLessThan(0);
    expect(edgeDelta(990, 0, 1000)).toBeGreaterThan(0);
  });

  it("scrolls faster the closer the pointer is to the edge", () => {
    expect(Math.abs(edgeDelta(5, 0, 1000))).toBeGreaterThan(Math.abs(edgeDelta(40, 0, 1000)));
    expect(edgeDelta(995, 0, 1000)).toBeGreaterThan(edgeDelta(960, 0, 1000));
  });

  it("never scrolls faster than the limit, even when the pointer is past the edge", () => {
    expect(edgeDelta(-500, 0, 1000)).toBe(-MAX_STEP);
    expect(edgeDelta(5000, 0, 1000)).toBe(MAX_STEP);
    expect(edgeDelta(0, 0, 1000)).toBe(-MAX_STEP);
  });

  it("is symmetrical", () => {
    expect(edgeDelta(20, 0, 1000)).toBe(-edgeDelta(980, 0, 1000));
  });

  it("works for an area that does not start at zero", () => {
    expect(edgeDelta(310, 300, 900)).toBeLessThan(0);
    expect(edgeDelta(600, 300, 900)).toBe(0);
    expect(edgeDelta(895, 300, 900)).toBeGreaterThan(0);
  });

  it("does nothing in an area too small to have two edges", () => {
    expect(edgeDelta(10, 0, 100)).toBe(0);
    expect(edgeDelta(10, 0, 0)).toBe(0);
    expect(edgeDelta(10, 50, 20)).toBe(0);
  });

  it("takes the zone and the maximum as options", () => {
    expect(edgeDelta(10, 0, 1000, 100, 50)).toBe(-45);
    expect(edgeDelta(300, 0, 1000, 100, 50)).toBe(0);
  });
});
