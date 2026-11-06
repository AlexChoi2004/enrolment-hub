import type { Dashboard } from "../contract";
import { plural } from "../format";

export function Graduation({ graduation }: { graduation: Dashboard["graduation"] }) {
  return (
    <section className="dash-card dash-grad" aria-labelledby="dash-grad">
      <h2 id="dash-grad">Projected graduation</h2>
      {graduation.finished ? (
        <p className="dash-grad-session">Everything is done or in progress.</p>
      ) : (
        <>
          <p className="dash-grad-session">{graduation.session}</p>
          <p className="dash-muted">
            {graduation.sessions_left === 0 ? "This is the last session you need" : `${plural(graduation.sessions_left, "more session")} after the current one`},
            {" "}if you fill each session with 24 credit points. {graduation.remaining_cp} cp still to enrol in.
          </p>
        </>
      )}
    </section>
  );
}
