import { describe, expect, it } from "vitest";
import { BoardSchema, CARD_STATES, MoveResponseSchema, parseBoard } from "./contract";
import { allBoardFixtures, boardRaw, moveRaw } from "../test/helpers";

describe("what the server really sends for the board", () => {
  it("has a board for each of the four starting points", () => {
    expect(allBoardFixtures).toHaveLength(4);
  });
  it.each(allBoardFixtures)("%s matches the contract", (_name, json) => {
    expect(() => parseBoard(json)).not.toThrow();
  });
  it("matches for a successful move, a refusal and a bad request", () => {
    expect(MoveResponseSchema.safeParse(moveRaw("ok")).success).toBe(true);
    expect(MoveResponseSchema.safeParse(moveRaw("refused")).success).toBe(true);
    expect(MoveResponseSchema.safeParse(moveRaw("bad")).success).toBe(true);
  });
  it("has ten sessions, each with room for 24 credit points", () => {
    const board = parseBoard(boardRaw("sample"));
    expect(board.columns).toHaveLength(10);
    expect(board.columns.every((c) => c.capacity_cp === 24)).toBe(true);
  });
});

describe("the contract is strict", () => {
  const mutate = (change: (b: Record<string, any>) => void) => {
    const data = boardRaw("failed") as Record<string, any>;
    change(data);
    return BoardSchema.safeParse(data);
  };
  it("rejects a missing or extra key", () => {
    expect(mutate((b) => delete b.columns).success).toBe(false);
    expect(mutate((b) => (b.extra = 1)).success).toBe(false);
    expect(mutate((b) => delete b.to_place[0].valid_sessions).success).toBe(false);
    expect(mutate((b) => (b.columns[0].cards = [{ ...b.to_place[0], surprise: true }])).success).toBe(false);
  });
  it("rejects a card state it does not know", () => {
    expect(mutate((b) => (b.to_place[0].state = "dragged")).success).toBe(false);
    expect([...CARD_STATES]).toEqual(["enrolled", "planned", "todo", "stranded"]);
  });
  it("rejects negative or fractional credit points and loads", () => {
    expect(mutate((b) => (b.to_place[0].credit_points = -6)).success).toBe(false);
    expect(mutate((b) => (b.columns[0].load_cp = 7.5)).success).toBe(false);
  });
  it("tells a success from a refusal by its ok flag and does not let them mix", () => {
    const ok = moveRaw("ok") as Record<string, any>;
    expect(MoveResponseSchema.safeParse({ ...ok, ok: false }).success).toBe(false); // ok:false must not carry a board
    expect(MoveResponseSchema.safeParse({ ok: true, message: "x" }).success).toBe(false); // ok:true must carry one
    expect(MoveResponseSchema.safeParse({ ok: false, error: "no", board: ok.board }).success).toBe(false);
    expect(MoveResponseSchema.safeParse({ ok: "yes", error: "no" }).success).toBe(false);
  });
});
