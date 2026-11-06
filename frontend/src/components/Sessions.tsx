import type { Session } from "../contract";
import { plural } from "../format";
import { ProgressBar } from "./ProgressBar";

const SESSION_CP = 24;

export function Sessions({ sessions }: { sessions: readonly Session[] }) {
  return (
    <section className="dash-card" aria-labelledby="dash-sessions">
      <h2 id="dash-sessions">Sessions ahead</h2>
      <ul className="dash-sessions">
        {sessions.map((s) => (
          <li key={s.label} className="dash-session">
            <div className="dash-session-head">
              <strong>{s.label}</strong>
              {s.current ? <span className="dash-pill dash-pill-current">Current</span> : null}
              <span className={`dash-pill dash-wl-${s.workload ?? "unknown"}`}>{s.workload_label}</span>
            </div>
            <ProgressBar label={`${s.label} load`} total={SESSION_CP} segments={{ completed: 0, enrolled: s.enrolled > 0 ? s.load_cp : 0, planned: 0 }} unit="credit points of study" />
            <span className="dash-muted">
              {s.load_cp} of {SESSION_CP} cp · {plural(s.enrolled, "enrolled subject")}, {s.planned} planned
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
