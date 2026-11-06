import { type DragEvent, type ReactNode } from "react";
import { plural } from "../format";
import { ProgressBar } from "../components/ProgressBar";
import type { BoardCard, BoardColumn } from "./contract";

const STATE_LABEL: Record<BoardCard["state"], string> = {
  enrolled: "Enrolled (locked)", planned: "Planned", todo: "To place", stranded: "Needs rescheduling",
};
export const REMOVE = "__remove__";

interface CardProps {
  card: BoardCard;
  busy: boolean;
  refused: boolean;
  onDragStart: (code: string, event: DragEvent<HTMLElement>) => void;
  onDragEnd: () => void;
  onMove: (code: string, to: string | null) => void;
}

/** One subject. Enrolled subjects are locked; the rest can be dragged, or moved with the menu (which needs no mouse). */
export function Card({ card, busy, refused, onDragStart, onDragEnd, onMove }: CardProps) {
  const movable = card.state !== "enrolled";
  const classes = ["board-card", `board-card-${card.state}`, busy ? "board-card-busy" : "", refused ? "board-card-refused" : ""].filter(Boolean).join(" ");
  const canRemove = card.state === "planned" || card.state === "stranded";
  const menuId = `move-${card.code}`;
  return (
    <li
      className={classes}
      draggable={movable && !busy}
      aria-busy={busy}
      onDragStart={movable ? (event) => onDragStart(card.code, event) : undefined}
      onDragEnd={onDragEnd}
    >
      <div className="board-card-top">
        <span className="board-card-code">{card.code}</span>
        <span className="board-card-cp">{card.credit_points} cp</span>
      </div>
      <strong className="board-card-name">{card.name}</strong>
      <div className="board-card-tags">
        <span className="dash-pill">{STATE_LABEL[card.state]}</span>
        {card.retake ? <span className="dash-pill dash-wl-heavy">Retake</span> : null}
      </div>
      {card.problem ? <p className="board-card-problem">{card.problem}</p> : null}
      {movable ? (
        card.valid_sessions.length > 0 || canRemove ? (
          <div className="board-card-menu">
            <label htmlFor={menuId} className="dash-sr">Move {card.code} {card.name} to</label>
            <select id={menuId} value="" disabled={busy} onChange={(event) => event.target.value && onMove(card.code, event.target.value === REMOVE ? null : event.target.value)}>
              <option value="">Move to…</option>
              {card.valid_sessions.map((label) => <option key={label} value={label}>{label}</option>)}
              {canRemove ? <option value={REMOVE}>Take out of my plan</option> : null}
            </select>
          </div>
        ) : (
          <p className="dash-muted board-card-hint">No session fits yet. Try dragging it to see why.</p>
        )
      ) : null}
    </li>
  );
}

interface ColumnProps {
  title: ReactNode;
  column?: BoardColumn;
  count: number;
  note?: string;
  /** When a card is being dragged: does this column accept it according to the server? */
  state: "idle" | "valid" | "invalid";
  over: boolean;
  onDragOver: (event: DragEvent<HTMLElement>) => void;
  onDragLeave: () => void;
  onDrop: (event: DragEvent<HTMLElement>) => void;
  children: ReactNode;
}

export function Column({ title, column, count, note, state, over, onDragOver, onDragLeave, onDrop, children }: ColumnProps) {
  const classes = ["board-col", state !== "idle" ? `board-col-${state}` : "", over ? "board-col-over" : "", column?.current ? "board-col-current" : ""].filter(Boolean).join(" ");
  return (
    <section className={classes} aria-label={typeof title === "string" ? title : undefined} onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}>
      <header className="board-col-head">
        <h2 className="board-col-title">{title}</h2>
        {column ? (
          <>
            <div className="board-col-pills">
              {column.current ? <span className="dash-pill dash-pill-current">Current</span> : null}
              <span className={`dash-pill dash-wl-${column.workload ?? "unknown"}`}>{column.workload_label}</span>
            </div>
            <ProgressBar label={`${column.label} load`} total={column.capacity_cp} segments={{ completed: 0, enrolled: column.load_cp, planned: 0 }} unit="credit points of study" />
            <span className="dash-muted">{column.load_cp} of {column.capacity_cp} cp · {plural(count, "subject")}</span>
          </>
        ) : (
          <span className="dash-muted">{plural(count, "subject")}{note ? ` · ${note}` : ""}</span>
        )}
      </header>
      <ul className="board-cards">{children}</ul>
    </section>
  );
}
