import { percent } from "../format";

export interface Segments {
  completed: number;
  enrolled: number;
  planned: number;
}

interface Props {
  label: string;
  total: number;
  segments: Segments;
  /** Words for the numbers, read out by screen readers: "60 of 96 credit points". */
  unit?: string;
}

/**
 * A bar split into done, in progress and planned. The three kinds look different (solid, lighter, striped) and are named in the
 * accessible text, so colour is never the only signal.
 */
export function ProgressBar({ label, total, segments, unit = "credit points" }: Props) {
  const done = segments.completed + segments.enrolled;
  const text = `${done} of ${total} ${unit}: ${segments.completed} completed, ${segments.enrolled} in progress, ${segments.planned} planned`;
  return (
    <div
      className="dash-bar"
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={total}
      aria-valuenow={Math.min(done, total)}
      aria-valuetext={text}
    >
      <span className="dash-seg dash-seg-completed" style={{ width: `${percent(segments.completed, total)}%` }} />
      <span className="dash-seg dash-seg-enrolled" style={{ width: `${percent(segments.enrolled, total)}%` }} />
      <span className="dash-seg dash-seg-planned" style={{ width: `${percent(segments.planned, total)}%` }} />
    </div>
  );
}

export function Legend() {
  return (
    <ul className="dash-legend" aria-label="Key">
      <li><span className="dash-swatch dash-seg-completed" aria-hidden="true" /> Completed</li>
      <li><span className="dash-swatch dash-seg-enrolled" aria-hidden="true" /> In progress</li>
      <li><span className="dash-swatch dash-seg-planned" aria-hidden="true" /> Planned</li>
    </ul>
  );
}
