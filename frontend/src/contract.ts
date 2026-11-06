import { z } from "zod";

/**
 * The shape of GET /api/dashboard. This file is one half of a contract: the other half is features/dashboard/service.py.
 * Every object is strict, so a key the server adds or drops fails here, and a Python test fails if the checked-in
 * fixtures in src/test/fixtures no longer match what the server sends. The server decides; this page only displays.
 */
const int = z.number().int().nonnegative();
/** A link to a page on this site: starts with one "/" and not "//" or "/\\", which browsers read as another site. */
export const SAME_SITE_PATH = /^\/(?![/\\])/;

export const WORKLOADS = ["light", "balanced", "heavy", "too_heavy"] as const;
export const STEP_KINDS = ["setup", "retake", "blocked", "reschedule", "workload", "enrol", "plan"] as const;

const Category = z
  .object({ key: z.string(), label: z.string(), required_cp: int, completed_cp: int, enrolled_cp: int, planned_cp: int, pending: z.boolean() })
  .strict();

const Session = z
  .object({
    label: z.string(), current: z.boolean(), load_cp: int, enrolled: int, planned: int,
    workload: z.enum(WORKLOADS).nullable(), workload_label: z.string(),
  })
  .strict();

const Step = z
  .object({ kind: z.enum(STEP_KINDS), severity: z.enum(["info", "warning"]), text: z.string(), href: z.string().regex(SAME_SITE_PATH) })
  .strict();

export const DashboardSchema = z
  .object({
    student: z.object({ display_name: z.string() }).strict(),
    period: z.object({ label: z.string(), year: int, semester: int }).strict(),
    degree: z.object({ total_cp: int, completed_cp: int, enrolled_cp: int, planned_cp: int, remaining_cp: int }).strict(),
    counts: z.object({ completed: int, enrolled: int, planned: int, retake: int, blocked: int }).strict(),
    choices: z
      .object({
        major: z.object({ name: z.string().nullable() }).strict(),
        pathway: z.object({ kind: z.enum(["submajor", "electives"]).nullable(), name: z.string().nullable() }).strict(),
      })
      .strict(),
    categories: z.array(Category),
    graduation: z.object({ session: z.string(), sessions_left: int, remaining_cp: int, finished: z.boolean() }).strict(),
    sessions: z.array(Session),
    next_steps: z.array(Step),
  })
  .strict();

export type Dashboard = z.infer<typeof DashboardSchema>;
export type Category = Dashboard["categories"][number];
export type Session = Dashboard["sessions"][number];
export type Step = Dashboard["next_steps"][number];
export type Workload = (typeof WORKLOADS)[number];

/** Parse anything into a Dashboard, or throw a readable error. */
export function parseDashboard(input: unknown): Dashboard {
  return DashboardSchema.parse(input);
}
