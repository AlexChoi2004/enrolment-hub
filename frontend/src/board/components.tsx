import { Fragment, type DragEvent, type ReactNode } from "react";
import { plural } from "../format";
import { ProgressBar } from "../components/ProgressBar";
import type { BoardCard, BoardColumn, BoardGroup } from "./contract";

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
      {card.category_key && (card.state === "planned" || card.state === "enrolled") ? <span className={`badge category cat-${card.category_key} board-card-category`}>{card.category}</span> : null}
      <div className="board-card-tags">
        {card.state === "enrolled" || card.state === "stranded" ? <span className="dash-pill">{STATE_LABEL[card.state]}</span> : <span className="dash-sr">{STATE_LABEL[card.state]}.</span>}
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
  /** Extra controls under the title, for example the filter box. */
  extra?: ReactNode;
  /** When a card is being dragged: does this column accept it according to the server? */
  state: "idle" | "valid" | "invalid";
  over: boolean;
  onDragOver: (event: DragEvent<HTMLElement>) => void;
  onDragLeave: () => void;
  onDrop: (event: DragEvent<HTMLElement>) => void;
  children: ReactNode;
}

export function Column({ title, column, count, note, extra, state, over, onDragOver, onDragLeave, onDrop, children }: ColumnProps) {
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
        {extra}
      </header>
      <ul className="board-cards">{children}</ul>
    </section>
  );
}

export const ALL = "all";

function hint(group: BoardGroup): string {
  if (group.kind === "choose" && group.need !== null && group.choose !== null && group.chosen !== null) {
    return ` · choose ${group.need} more (${group.chosen} of ${group.choose} chosen)`;
  }
  return ` (${group.count})`;
}

interface ToPlaceProps {
  cards: readonly BoardCard[];
  groups: readonly BoardGroup[];
  /** The text typed in the filter box. */
  query: string;
  /** ALL, or the key of one requirement. */
  category: string;
  renderCard: (card: BoardCard) => ReactNode;
}

/**
 * The to-place list, grouped by requirement. Within each requirement what can be placed now comes first, and what is waiting on
 * other subjects is folded away. A subject whose session has passed is listed first, under its own heading.
 */
export function ToPlaceList({ cards, groups, query, category, renderCard }: ToPlaceProps) {
  const needle = query.trim().toLowerCase();
  const matches = (card: BoardCard) => !needle || card.code.toLowerCase().includes(needle) || card.name.toLowerCase().includes(needle);
  const stranded = category === ALL ? cards.filter((c) => c.state === "stranded" && matches(c)) : [];
  const sections = groups
    .filter((g) => category === ALL || g.key === category)
    .map((g) => {
      const mine = cards.filter((c) => c.state === "todo" && c.category === g.label && matches(c));
      return { group: g, ready: mine.filter((c) => c.valid_sessions.length > 0), waiting: mine.filter((c) => c.valid_sessions.length === 0) };
    })
    .filter((s) => s.ready.length + s.waiting.length > 0);
  const shown = stranded.length + sections.length;
  return (
    <>
      {stranded.length > 0 ? <li className="board-group-title">Needs rescheduling</li> : null}
      {stranded.map(renderCard)}
      {sections.map(({ group, ready, waiting }) => (
        <Fragment key={group.key}>
          <li className={`board-group-title cat-${group.key}`}>{group.label}{hint(group)}</li>
          {ready.map(renderCard)}
          {waiting.length > 0 ? (
            <li className="board-waiting">
              <details open={Boolean(needle)}>
                <summary>Waiting on other subjects ({waiting.length})</summary>
                <ul className="board-cards">{waiting.map(renderCard)}</ul>
              </details>
            </li>
          ) : null}
        </Fragment>
      ))}
      {shown === 0 ? <li className="dash-muted board-empty">{needle ? "No subject matches that filter." : "Everything is placed."}</li> : null}
    </>
  );
}
