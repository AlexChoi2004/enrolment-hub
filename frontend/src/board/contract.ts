import { z } from "zod";
import { SAME_SITE_PATH, WORKLOADS } from "../contract";

/**
 * The shape of GET /api/planner/board and of the answer to POST /api/planner/move. One half of a contract with
 * features/degree_planner/board.py and api.py: every object is strict, and fixtures made from the real server data are checked from
 * both sides. The server decides what is allowed; this page only shows the plan and asks.
 */
const int = z.number().int().nonnegative();
export const CARD_STATES = ["enrolled", "planned", "todo", "stranded"] as const;

const Card = z
  .object({
    code: z.string(), name: z.string(), credit_points: int, category: z.string().nullable(), category_key: z.string().nullable(),
    state: z.enum(CARD_STATES), problem: z.string().nullable(), retake: z.boolean(),
    /** The sessions the planner would accept this subject in right now (empty for an enrolled subject). */
    valid_sessions: z.array(z.string()),
  })
  .strict();

const Column = z
  .object({
    label: z.string(), current: z.boolean(), capacity_cp: int, load_cp: int,
    workload: z.enum(WORKLOADS).nullable(), workload_label: z.string(), cards: z.array(Card),
  })
  .strict();

/** One requirement that still has something to place, in the degree's own order. A "choose" group is pick-some-of-these (electives). */
const Group = z
  .object({
    key: z.string(), label: z.string(), kind: z.enum(["required", "choose"]), count: int,
    choose: int.nullable(), chosen: int.nullable(), need: int.nullable(),
  })
  .strict();

const ChooseFirst = z.object({ label: z.string(), href: z.string().regex(SAME_SITE_PATH) }).strict();

export const BoardSchema = z
  .object({
    period: z.object({ label: z.string(), year: int, semester: int }).strict(),
    capacity_cp: int, columns: z.array(Column), to_place: z.array(Card), groups: z.array(Group), choose_first: z.array(ChooseFirst),
  })
  .strict();

export const MoveResponseSchema = z.discriminatedUnion("ok", [
  z.object({ ok: z.literal(true), message: z.string(), board: BoardSchema }).strict(),
  z.object({ ok: z.literal(false), error: z.string() }).strict(),
]);

export type Board = z.infer<typeof BoardSchema>;
export type BoardCard = Board["to_place"][number];
export type BoardGroup = Board["groups"][number];
export type BoardColumn = Board["columns"][number];
export type CardState = (typeof CARD_STATES)[number];
export type MoveResponse = z.infer<typeof MoveResponseSchema>;

export function parseBoard(input: unknown): Board {
  return BoardSchema.parse(input);
}
