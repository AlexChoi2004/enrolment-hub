import type { Category } from "../contract";
import { ProgressBar } from "./ProgressBar";

export function Requirements({ categories }: { categories: readonly Category[] }) {
  return (
    <section className="dash-card" aria-labelledby="dash-req">
      <h2 id="dash-req">Requirements</h2>
      <ul className="dash-reqs">
        {categories.map((c) => (
          <li key={c.key} className={c.pending ? "dash-req dash-req-pending" : "dash-req"}>
            <div className="dash-req-head">
              <span>{c.label}</span>
              <span className="dash-req-numbers">{c.completed_cp + c.enrolled_cp} / {c.required_cp} cp</span>
            </div>
            <ProgressBar label={c.label} total={c.required_cp} segments={{ completed: c.completed_cp, enrolled: c.enrolled_cp, planned: c.planned_cp }} />
          </li>
        ))}
      </ul>
    </section>
  );
}
