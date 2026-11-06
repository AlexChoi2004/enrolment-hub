import type { Dashboard } from "../contract";
import { cp, plural } from "../format";

export function StatCards({ degree, counts }: Pick<Dashboard, "degree" | "counts">) {
  const cards = [
    { key: "completed", label: "Completed", value: cp(degree.completed_cp), note: plural(counts.completed, "subject") },
    { key: "enrolled", label: "In progress", value: cp(degree.enrolled_cp), note: plural(counts.enrolled, "subject") },
    { key: "planned", label: "Planned", value: cp(degree.planned_cp), note: plural(counts.planned, "subject") },
    { key: "remaining", label: "Still to plan", value: cp(degree.remaining_cp), note: `of ${degree.total_cp} cp` },
  ];
  return (
    <ul className="dash-cards" aria-label="Credit points">
      {cards.map((card) => (
        <li key={card.key} className="dash-card dash-stat">
          <span className="dash-stat-label">{card.label}</span>
          <strong className="dash-stat-value">{card.value}</strong>
          <span className="dash-stat-note">{card.note}</span>
        </li>
      ))}
    </ul>
  );
}
