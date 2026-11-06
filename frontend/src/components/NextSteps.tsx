import type { Step } from "../contract";

export function NextSteps({ steps }: { steps: readonly Step[] }) {
  return (
    <section className="dash-card" aria-labelledby="dash-steps">
      <h2 id="dash-steps">Next steps</h2>
      {steps.length === 0 ? (
        <p className="dash-muted">Nothing needs your attention right now.</p>
      ) : (
        <ul className="dash-steps">
          {steps.map((s, i) => (
            <li key={`${s.kind}-${i}`} className={`dash-step dash-step-${s.severity}`}>
              <span className="dash-step-icon" aria-hidden="true">{s.severity === "warning" ? "!" : "›"}</span>
              <a href={s.href}>
                <span className="dash-sr">{s.severity === "warning" ? "Needs attention: " : ""}</span>
                {s.text}
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
