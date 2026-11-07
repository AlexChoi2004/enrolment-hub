import { type DragEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { type BoardLoaded, loadBoard, moveCard } from "./api";
import { ALL, Card, Column, ToPlaceList } from "./components";
import type { Board, BoardCard } from "./contract";
import { edgeDelta } from "./scroll";

type Announcement = { kind: "ok" | "refused" | "error"; text: string; loginNeeded?: boolean } | null;
type Loading = { status: "loading" };

export interface BoardProps {
  boardEndpoint: string;
  moveEndpoint: string;
  csrf: string;
  fetchImpl?: typeof fetch;
}

export function BoardApp({ boardEndpoint, moveEndpoint, csrf, fetchImpl }: BoardProps) {
  const [loaded, setLoaded] = useState<Loading | BoardLoaded>({ status: "loading" });
  useEffect(() => {
    const controller = new AbortController();
    loadBoard(boardEndpoint, fetchImpl, controller.signal).then(setLoaded, () => undefined);
    return () => controller.abort();
  }, [boardEndpoint, fetchImpl]);

  if (loaded.status === "loading") return <p className="dash-muted" role="status" aria-live="polite">Loading your plan…</p>;
  if (loaded.status === "error") {
    return (
      <div className="dash-card dash-error" role="alert">
        <p>{loaded.message}</p>
        {loaded.loginNeeded ? <p><a href="/login">Go to the login page</a></p> : <p><a href="/planner">Use the classic planner</a></p>}
      </div>
    );
  }
  return <BoardView initial={loaded.board} moveEndpoint={moveEndpoint} csrf={csrf} {...(fetchImpl ? { fetchImpl } : {})} />;
}

interface BoardInnerProps {
  initial: Board;
  moveEndpoint: string;
  csrf: string;
  fetchImpl?: typeof fetch;
}

export function BoardView({ initial, moveEndpoint, csrf, fetchImpl }: BoardInnerProps) {
  const [board, setBoard] = useState(initial);
  const [dragging, setDragging] = useState<string | null>(null);
  const [over, setOver] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [refused, setRefused] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState<Announcement>(null);
  const [focusAfter, setFocusAfter] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [category, setCategory] = useState(ALL);
  const scroller = useRef<HTMLDivElement>(null);

  const cards = useMemo(() => new Map<string, BoardCard>([...board.to_place, ...board.columns.flatMap((c) => c.cards)].map((c) => [c.code, c])), [board]);
  const locations = useMemo(() => new Map<string, string | null>([...board.to_place.map((c) => [c.code, null] as const), ...board.columns.flatMap((c) => c.cards.map((card) => [card.code, c.label] as const))]), [board]);
  const draggedCard = dragging ? cards.get(dragging) : undefined;

  useEffect(() => {  // after a move the card is somewhere else: put keyboard focus on it there, so a keyboard user is not dropped back at the top
    if (!focusAfter) return;
    document.getElementById(`move-${focusAfter}`)?.focus();
    setFocusAfter(null);
  }, [focusAfter, board]);

  useEffect(() => {  // the shake is a short cue; take the marker off afterwards (a timer, so it also works where animation events do not fire)
    if (!refused) return;
    const timer = setTimeout(() => setRefused(null), 700);
    return () => clearTimeout(timer);
  }, [refused]);

  const perform = useCallback(async (code: string, to: string | null) => {
    if (busy) return;
    setBusy(code);
    setAnnouncement(null);
    const outcome = await moveCard(moveEndpoint, csrf, code, to, fetchImpl);
    setBusy(null);
    if (outcome.status === "moved") {
      setBoard(outcome.board);
      setFocusAfter(code);
      setAnnouncement({ kind: "ok", text: outcome.message });
    } else if (outcome.status === "refused") {
      setRefused(code); // the card stays where it was and shakes; the planner's own reason is shown
      setAnnouncement({ kind: "refused", text: outcome.message });
    } else {
      setAnnouncement({ kind: "error", text: outcome.message, loginNeeded: outcome.loginNeeded });
    }
  }, [busy, csrf, fetchImpl, moveEndpoint]);

  const dropOn = (to: string | null) => (event: DragEvent<HTMLElement>) => {
    event.preventDefault();
    const code = event.dataTransfer.getData("text/plain") || dragging;
    setOver(null);
    setDragging(null);
    if (!code || !cards.has(code)) return;
    const card = cards.get(code) as BoardCard;
    if (locations.get(code) === to) return; // dropped where it already is
    if (to === null && card.state === "todo") return; // it is not in the plan, so there is nothing to take out
    void perform(code, to);
  };
  /** While dragging near an edge, scroll the sessions sideways and the list under the pointer up or down. */
  const autoScroll = (event: DragEvent<HTMLElement>) => {
    if (!dragging) return;
    const box = scroller.current;
    if (box) {
      const rect = box.getBoundingClientRect();
      box.scrollLeft += edgeDelta(event.clientX, rect.left, rect.right);
    }
    const list = (event.target as HTMLElement | null)?.closest?.(".board-col")?.querySelector<HTMLElement>(".board-cards");
    if (list) {
      const rect = list.getBoundingClientRect();
      list.scrollTop += edgeDelta(event.clientY, rect.top, rect.bottom);
    }
  };
  const allowDrop = (label: string | null) => (event: DragEvent<HTMLElement>) => {
    if (!dragging) return;
    event.preventDefault(); // every column accepts the drop: an invalid one gets the planner's reason, which is the point
    setOver(label ?? "to-place");
  };
  const columnState = (label: string | null): "idle" | "valid" | "invalid" => {
    if (!draggedCard) return "idle";
    if (label === null) return draggedCard.state === "planned" || draggedCard.state === "stranded" ? "valid" : "invalid";
    return draggedCard.valid_sessions.includes(label) ? "valid" : "invalid";
  };
  const renderCard = (card: BoardCard) => (
    <Card
      key={card.code} card={card} busy={busy === card.code} refused={refused === card.code}
      onDragStart={(code, event) => { event.dataTransfer.setData("text/plain", code); event.dataTransfer.effectAllowed = "move"; setDragging(code); }}
      onDragEnd={() => { setDragging(null); setOver(null); }}
      onMove={(code, to) => void perform(code, to)}
    />
  );

  return (
    <div className="board">
      <p className="dash-muted board-help">
        Drag a card to a session, or use its <strong>Move to…</strong> menu. The planner checks every move and says why if it can&apos;t be done.
        Subjects you are enrolled in are locked.
      </p>
      {announcement ? (
        <div className={`board-announce board-announce-${announcement.kind}`} role={announcement.kind === "ok" ? "status" : "alert"}>
          {announcement.text}
          {announcement.loginNeeded ? <> <a href="/login">Go to the login page</a></> : null}
        </div>
      ) : <div className="board-announce-space" role="status" aria-live="polite" />}
      {board.choose_first.map((note) => (
        <p key={note.href} className="dash-muted board-note"><a href={note.href}>{note.label}</a></p>
      ))}
      <div className="board-scroll" ref={scroller} onDragOver={autoScroll}>
        <Column title="To place" count={board.to_place.length} note="drop a planned card here to take it out" state={columnState(null)} over={over === "to-place"}
                onDragOver={allowDrop(null)} onDragLeave={() => setOver(null)} onDrop={dropOn(null)}
                extra={
                  <>
                    <input type="search" className="board-filter" placeholder="Filter subjects…" aria-label="Filter subjects to place" value={filter}
                           onChange={(event) => setFilter(event.target.value)} />
                    <select className="board-category" aria-label="Show category" value={category} onChange={(event) => setCategory(event.target.value)}>
                      <option value={ALL}>All categories ({board.to_place.filter((c) => c.state === "todo").length})</option>
                      {board.groups.map((g) => <option key={g.key} value={g.key}>{g.label} ({g.count})</option>)}
                    </select>
                  </>
                }>
          <ToPlaceList cards={board.to_place} groups={board.groups} query={filter} category={category} renderCard={renderCard} />
        </Column>
        {board.columns.map((column) => (
          <Column key={column.label} title={column.label} column={column} count={column.cards.length} state={columnState(column.label)} over={over === column.label}
                  onDragOver={allowDrop(column.label)} onDragLeave={() => setOver(null)} onDrop={dropOn(column.label)}>
            {column.cards.map(renderCard)}
          </Column>
        ))}
      </div>
    </div>
  );
}
