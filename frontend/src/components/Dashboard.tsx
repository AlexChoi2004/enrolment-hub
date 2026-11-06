import type { Dashboard as DashboardData } from "../contract";
import { firstName, yearAndSemester } from "../format";
import { Graduation } from "./Graduation";
import { NextSteps } from "./NextSteps";
import { Legend, ProgressBar } from "./ProgressBar";
import { Requirements } from "./Requirements";
import { Sessions } from "./Sessions";
import { StatCards } from "./StatCards";

export function Dashboard({ data }: { data: DashboardData }) {
  const { degree, choices } = data;
  const pathway = choices.pathway.name ?? "No sub-major or electives chosen yet";
  return (
    <div className="dash">
      <header className="dash-hero">
        <div>
          <h2 className="dash-hello">Welcome back, {firstName(data.student.display_name)}</h2>
          <p className="dash-muted">
            {data.period.label} · {yearAndSemester(data.period.year, data.period.semester)}
          </p>
          <p className="dash-muted">
            {choices.major.name ?? "No major chosen yet"} · {pathway}
          </p>
        </div>
      </header>

      <section className="dash-card" aria-labelledby="dash-overall">
        <h2 id="dash-overall">Your degree</h2>
        <ProgressBar
          label="Degree progress"
          total={degree.total_cp}
          segments={{ completed: degree.completed_cp, enrolled: degree.enrolled_cp, planned: degree.planned_cp }}
        />
        <Legend />
      </section>

      <StatCards degree={data.degree} counts={data.counts} />
      <div className="dash-two">
        <Graduation graduation={data.graduation} />
        <NextSteps steps={data.next_steps} />
      </div>
      <Requirements categories={data.categories} />
      <Sessions sessions={data.sessions} />
    </div>
  );
}
