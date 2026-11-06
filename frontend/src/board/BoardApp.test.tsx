import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BoardApp, BoardView } from "./BoardApp";
import { type Board, parseBoard } from "./contract";
import { mountBoard } from "./main";
import { boardRaw, fakeFetch, jsonResponse, moveRaw } from "../test/helpers";

type Fetch = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

function dataTransfer() {
  const data: Record<string, string> = {};
  return { data, setData: (k: string, v: string) => { data[k] = v; }, getData: (k: string) => data[k] ?? "", effectAllowed: "", dropEffect: "" };
}

const failed = (): Board => parseBoard(boardRaw("failed"));
const cardOf = (name: string) => screen.getByText(name).closest("li") as HTMLElement;
const column = (name: string) => screen.getByRole("region", { name });

function show(board: Board, response: Response | (() => Promise<Response>) | Error = jsonResponse(moveRaw("ok"))) {
  const spy = vi.fn<Fetch>(async () => (response instanceof Error ? Promise.reject(response) : typeof response === "function" ? response() : response.clone()));
  render(<BoardView initial={board} moveEndpoint="/api/planner/move" csrf="tok" fetchImpl={spy as unknown as typeof fetch} />);
  return spy;
}

function drag(name: string, to: string) {
  const dt = dataTransfer();
  fireEvent.dragStart(cardOf(name), { dataTransfer: dt });
  fireEvent.dragOver(column(to), { dataTransfer: dt });
  fireEvent.drop(column(to), { dataTransfer: dt });
}

describe("the board", () => {
  it("shows the to-place column and one column per session, each with its load", () => {
    show(failed());
    expect(screen.getAllByRole("region")).toHaveLength(11);
    expect(column("Autumn 2027")).toHaveTextContent("Current");
    expect(column("Autumn 2027")).toHaveTextContent("18 of 24 cp · 3 subjects");
    expect(column("To place")).toHaveTextContent(`${failed().to_place.length} subjects`);
    expect(screen.getByRole("progressbar", { name: "Autumn 2027 load" })).toHaveAttribute("aria-valuemax", "24");
  });

  it("locks enrolled subjects: no dragging and no menu", () => {
    show(failed());
    const enrolled = cardOf("Communication for IT Professionals");
    expect(enrolled).toHaveAttribute("draggable", "false");
    expect(enrolled).toHaveTextContent("Enrolled (locked)");
    expect(within(enrolled).queryByRole("combobox")).toBeNull();
  });

  it("shows why a planned card is blocked, and marks a retake", () => {
    show(failed());
    expect(cardOf("Data Structures and Algorithms")).toHaveTextContent("failed: retake it first");
    expect(cardOf("Programming 2")).toHaveTextContent("Retake");
  });

  it("says when no session fits yet, instead of showing an empty menu", () => {
    show(parseBoard(boardRaw("fresh")));
    const stuck = screen.getAllByText(/No session fits yet/)[0] as HTMLElement;
    expect(stuck).toBeInTheDocument();
    expect(within(stuck.closest("li") as HTMLElement).queryByRole("combobox")).toBeNull();
  });

  it("tells students how many to choose in a pick-some-of-these requirement", () => {
    show(failed());
    expect(screen.getByText("Major electives · choose 3 more (0 of 3 chosen)")).toBeInTheDocument();
    expect(screen.getAllByText("Core subjects (8)")).toHaveLength(2); // the group heading and the category menu
  });

  it("offers the subjects to choose from, not only the required ones", () => {
    show(failed());
    const electives = failed().to_place.filter((c) => c.category_key === "major_elective");
    expect(electives.length).toBeGreaterThanOrEqual(8);
    for (const card of electives) expect(screen.getAllByText(card.name).length).toBeGreaterThan(0);
  });

  it("points a first-year to choosing a major and a sub-major, with links", () => {
    show(parseBoard(boardRaw("fresh")));
    expect(screen.getByRole("link", { name: "Choose your major to see its subjects here." })).toHaveAttribute("href", "/major");
    expect(screen.getByRole("link", { name: "Choose a sub-major or general electives to see their subjects here." })).toHaveAttribute("href", "/submajor");
  });

  it("labels cards in the sessions with their requirement, and keeps the to-place cards compact", () => {
    show(failed());
    expect(cardOf("Communication for IT Professionals").querySelector(".board-card-category")).toHaveTextContent("Core subjects");
    expect(cardOf("Programming 2").querySelector(".board-card-category")).toBeNull(); // the group heading already says it
  });

  it("escapes subject names instead of treating them as markup", () => {
    const board = failed();
    board.to_place[0] = { ...board.to_place[0]!, name: "<img src=x onerror=alert(1)> Evil" };
    const { container } = render(<BoardView initial={board} moveEndpoint="/m" csrf="t" />);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getAllByText(/<img src=x/).length).toBeGreaterThan(0);  // shown as plain text (in the card and in its menu label)
  });
});

describe("dragging", () => {
  it("highlights where the server says a card can go, and dims the rest", () => {
    show(failed());
    const dt = dataTransfer();
    fireEvent.dragStart(cardOf("Data Structures and Algorithms"), { dataTransfer: dt }); // planned, but blocked: no session fits
    expect(column("To place")).toHaveClass("board-col-valid"); // it can be taken out of the plan
    expect(column("Spring 2028")).toHaveClass("board-col-invalid");
    fireEvent.dragEnd(cardOf("Data Structures and Algorithms"));
    expect(column("To place")).not.toHaveClass("board-col-valid");
  });

  it("marks a column valid when the card's own list of sessions includes it", () => {
    show(failed());
    fireEvent.dragStart(cardOf("Programming 2"), { dataTransfer: dataTransfer() });
    expect(column("Spring 2027")).toHaveClass("board-col-valid");
    expect(column("To place")).toHaveClass("board-col-invalid"); // not in the plan, so nothing to take out
  });

  it("sends the move to the server, then shows the board exactly as the server returns it", async () => {
    const spy = show(failed());
    drag("Programming 2", "Spring 2027");
    await screen.findByRole("status", {}, { timeout: 2000 }).then((s) => expect(s).toHaveTextContent("Added 48024 Programming 2 to your plan for Spring 2027."));
    expect(spy).toHaveBeenCalledTimes(1);
    const [url, init] = spy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/planner/move");
    expect(JSON.parse(String(init.body))).toEqual({ code: "48024", to: "Spring 2027" });
    expect((init.headers as Record<string, string>)["X-CSRF-Token"]).toBe("tok");
    expect(within(column("Spring 2027")).getByText("Programming 2")).toBeInTheDocument();
    expect(within(column("To place")).queryByText("Programming 2")).toBeNull();
  });

  it("when the planner refuses, shows its reason, shakes the card and changes nothing", async () => {
    show(failed(), jsonResponse(moveRaw("refused"), { status: 422 }));
    drag("Programming 2", "Autumn 2029");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("31251 Data Structures and Algorithms is planned for Spring 2027 and needs 48024 Programming 2 first");
    expect(cardOf("Programming 2")).toHaveClass("board-card-refused");
    expect(within(column("To place")).getByText("Programming 2")).toBeInTheDocument(); // it never left
    await waitFor(() => expect(cardOf("Programming 2")).not.toHaveClass("board-card-refused"), { timeout: 2000 }); // the cue clears itself
  });

  it("does nothing when a card is dropped where it already is, or a to-place card is dropped on to-place", () => {
    const spy = show(failed());
    drag("Data Structures and Algorithms", "Spring 2027");
    drag("Programming 2", "To place");
    expect(spy).not.toHaveBeenCalled();
  });

  it("asks to take a planned card out of the plan when it is dropped on to-place", async () => {
    const spy = show(failed());
    drag("Data Structures and Algorithms", "To place");
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
    expect(JSON.parse(String((spy.mock.calls[0]?.[1] as RequestInit).body))).toEqual({ code: "31251", to: null });
  });

  it("ignores a second move while one is being checked", async () => {
    let release: (r: Response) => void = () => undefined;
    const spy = show(failed(), () => new Promise<Response>((resolve) => { release = resolve; }));
    drag("Programming 2", "Spring 2027");
    expect(cardOf("Programming 2")).toHaveAttribute("aria-busy", "true");
    drag("Data Structures and Algorithms", "To place");
    expect(spy).toHaveBeenCalledTimes(1);
    release(jsonResponse(moveRaw("ok")));
    await screen.findByRole("status");
  });

  it("ignores a drop of something that is not a subject on the board", () => {
    const spy = show(failed());
    fireEvent.drop(column("Spring 2027"), { dataTransfer: { getData: () => "99999", setData: () => undefined } });
    expect(spy).not.toHaveBeenCalled();
  });
});

describe("the menu, for anyone who cannot or does not want to drag", () => {
  it("lists only the sessions the server says are possible, and moves the card", async () => {
    const spy = show(failed());
    const menu = screen.getByLabelText("Move 48024 Programming 2 to");
    expect(within(menu).getAllByRole("option").map((o) => o.textContent)).toEqual(["Move to…", ...failed().to_place.find((c) => c.code === "48024")!.valid_sessions]);
    fireEvent.change(menu, { target: { value: "Spring 2027" } });
    await screen.findByText("Added 48024 Programming 2 to your plan for Spring 2027.");
    expect(JSON.parse(String((spy.mock.calls[0]?.[1] as RequestInit).body))).toEqual({ code: "48024", to: "Spring 2027" });
  });

  it("can take a planned subject out of the plan", async () => {
    const spy = show(failed());
    fireEvent.change(screen.getByLabelText("Move 31251 Data Structures and Algorithms to"), { target: { value: "__remove__" } });
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
    expect(JSON.parse(String((spy.mock.calls[0]?.[1] as RequestInit).body))).toEqual({ code: "31251", to: null });
  });

  it("is not offered to a subject that is not in the plan for taking out", () => {
    show(failed());
    const options = within(screen.getByLabelText("Move 48024 Programming 2 to")).getAllByRole("option").map((o) => o.textContent);
    expect(options).not.toContain("Take out of my plan");
  });
});

describe("when something goes wrong", () => {
  it("shows an error and changes nothing if the network fails", async () => {
    show(failed(), new TypeError("offline"));
    drag("Programming 2", "Spring 2027");
    expect(await screen.findByRole("alert")).toHaveTextContent("could not be sent");
    expect(within(column("To place")).getByText("Programming 2")).toBeInTheDocument();
  });

  it("offers a way back to the login page when the session has ended", async () => {
    show(failed(), jsonResponse("<html></html>", { redirected: true, contentType: "text/html" }));
    drag("Programming 2", "Spring 2027");
    expect(await screen.findByRole("alert")).toHaveTextContent("Your session has ended");
    expect(screen.getByRole("link", { name: "Go to the login page" })).toHaveAttribute("href", "/login");
  });
});

describe("BoardApp", () => {
  const props = { boardEndpoint: "/api/planner/board", moveEndpoint: "/api/planner/move", csrf: "tok" };

  it("loads the board, then shows it", async () => {
    render(<BoardApp {...props} fetchImpl={fakeFetch(jsonResponse(boardRaw("failed")))} />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading your plan…");
    expect(await screen.findByRole("region", { name: "Spring 2027" })).toBeInTheDocument();
  });

  it("shows the classic planner as a fallback when the board cannot load", async () => {
    render(<BoardApp {...props} fetchImpl={fakeFetch(jsonResponse({}, { status: 500 }))} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("error 500");
    expect(screen.getByRole("link", { name: "Use the classic planner" })).toHaveAttribute("href", "/planner");
  });

  it("offers the login page when the session has ended", async () => {
    render(<BoardApp {...props} fetchImpl={fakeFetch(jsonResponse("<html></html>", { redirected: true, contentType: "text/html" }))} />);
    expect(await screen.findByRole("link", { name: "Go to the login page" })).toBeInTheDocument();
  });

  it("does not update after it has been removed", async () => {
    let release: (r: Response) => void = () => undefined;
    const errors = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const view = render(<BoardApp {...props} fetchImpl={fakeFetch(() => new Promise<Response>((resolve) => { release = resolve; }))} />);
    view.unmount();
    release(jsonResponse(boardRaw("failed")));
    await waitFor(() => expect(errors).not.toHaveBeenCalled());
    errors.mockRestore();
  });
});

describe("mountBoard", () => {
  it("renders into the element the Flask page provides, using its data attributes", async () => {
    const root = document.createElement("div");
    Object.assign(root.dataset, { boardEndpoint: "/api/planner/board", moveEndpoint: "/api/planner/move", csrf: "tok" });
    document.body.appendChild(root);
    mountBoard(root, fakeFetch(jsonResponse(boardRaw("failed"))));
    expect(await screen.findByRole("region", { name: "To place" })).toBeInTheDocument();
    root.remove();
  });

  it("does nothing when any attribute is missing", () => {
    const root = document.createElement("div");
    Object.assign(root.dataset, { boardEndpoint: "/a", moveEndpoint: "/b" }); // no token
    expect(() => mountBoard(root)).not.toThrow();
    expect(() => mountBoard(null)).not.toThrow();
    expect(root.innerHTML).toBe("");
  });
});

describe("a long to-place list stays manageable", () => {
  const sample = () => parseBoard(boardRaw("sample"));
  const todo = (b: Board, key: string) => b.to_place.filter((c) => c.state === "todo" && c.category_key === key);
  const headings = () => screen.getAllByRole("listitem").filter((li) => li.className.includes("board-group-title")).map((li) => li.textContent);

  it("groups the list by requirement, in the degree's own order", () => {
    show(sample());
    expect(headings()).toEqual(["Core subjects (6)", "Honours core (2)", "Major core (1)", "Major electives · choose 2 more (1 of 3 chosen)"]);
  });

  it("puts what can be placed now first inside each group, and folds away what is waiting on other subjects", () => {
    const board = sample();
    show(board);
    const waiting = todo(board, "major_elective").filter((c) => c.valid_sessions.length === 0);
    expect(waiting.length).toBeGreaterThan(0);
    const details = cardOf(waiting[0]!.name).closest("details") as HTMLDetailsElement; // each group has its own fold
    expect(within(details).getByText(`Waiting on other subjects (${waiting.length})`)).toBeInTheDocument();
    expect(details.open).toBe(false);
    for (const card of waiting) expect(details).toContainElement(cardOf(card.name));
    const ready = todo(board, "major_elective").find((c) => c.valid_sessions.length > 0)!;
    expect(details).not.toContainElement(cardOf(ready.name));
  });

  it("counts every subject in the column heading, and every group in the category menu", () => {
    const board = sample();
    show(board);
    expect(column("To place")).toHaveTextContent(`${board.to_place.length} subjects`);
    const options = within(screen.getByRole("combobox", { name: "Show category" })).getAllByRole("option").map((o) => o.textContent);
    expect(options).toEqual([`All categories (${board.to_place.length})`, "Core subjects (6)", "Honours core (2)", "Major core (1)", "Major electives (8)"]);
  });

  it("shows one requirement at a time when a category is chosen", () => {
    const board = sample();
    show(board);
    fireEvent.change(screen.getByRole("combobox", { name: "Show category" }), { target: { value: "major_elective" } });
    expect(headings()).toEqual(["Major electives · choose 2 more (1 of 3 chosen)"]);
    const core = todo(board, "core")[0]!;
    expect(screen.queryByText(core.name)).toBeNull();
    for (const card of todo(board, "major_elective")) expect(screen.getAllByText(card.name).length).toBeGreaterThan(0);
    fireEvent.change(screen.getByRole("combobox", { name: "Show category" }), { target: { value: "all" } });
    expect(headings()).toHaveLength(4);
  });

  it("filters by name or code across the groups, and opens the waiting group when the match is in it", () => {
    const board = sample();
    show(board);
    const filter = screen.getByRole("searchbox", { name: "Filter subjects to place" });
    const waiting = todo(board, "major_elective").find((c) => c.valid_sessions.length === 0)!;
    fireEvent.change(filter, { target: { value: waiting.code } });
    expect(screen.getAllByText(waiting.name).length).toBeGreaterThan(0);
    expect((cardOf(waiting.name).closest("details") as HTMLDetailsElement).open).toBe(true);
    expect(headings()).toEqual(["Major electives · choose 2 more (1 of 3 chosen)"]);
    fireEvent.change(filter, { target: { value: waiting.name.toUpperCase() } });
    expect(screen.getAllByText(waiting.name).length).toBeGreaterThan(0);
  });

  it("says so when nothing matches, and shows everything again when the filter is cleared", () => {
    show(sample());
    const filter = screen.getByRole("searchbox", { name: "Filter subjects to place" });
    fireEvent.change(filter, { target: { value: "zzzz-no-such-subject" } });
    expect(screen.getByText("No subject matches that filter.")).toBeInTheDocument();
    fireEvent.change(filter, { target: { value: "" } });
    expect(screen.queryByText("No subject matches that filter.")).toBeNull();
    expect(headings()).toHaveLength(4);
  });

  it("lists a subject whose session has passed first, under its own heading, whatever the category chosen", () => {
    const board = sample();
    board.to_place[0] = { ...board.to_place[0]!, state: "stranded", category: null, category_key: null, problem: "Planned for Autumn 2025, which has passed.", valid_sessions: ["Spring 2027"] };
    show(board);
    expect(headings()[0]).toBe("Needs rescheduling");
    expect(screen.getAllByText(/which has passed/).length).toBeGreaterThan(0);
  });

  it("says everything is placed when there is nothing left to place", () => {
    const board = sample();
    board.to_place = [];
    board.groups = [];
    show(board);
    expect(screen.getByText("Everything is placed.")).toBeInTheDocument();
  });

  it("drops tags that repeat what the column already says, but screen readers still hear them", () => {
    show(failed());
    const planned = cardOf("Data Structures and Algorithms");
    expect(within(planned).queryByText("Planned", { selector: ".dash-pill" })).toBeNull();
    expect(planned).toHaveTextContent("Planned.");
    const todoCard = cardOf("Programming 2");
    expect(within(todoCard).queryByText("To place", { selector: ".dash-pill" })).toBeNull();
    expect(todoCard.querySelector(".dash-sr")).toHaveTextContent("To place.");
    expect(cardOf("Communication for IT Professionals").querySelector(".dash-pill")).toHaveTextContent("Enrolled (locked)");
  });

  it("lets a student choose an elective by dragging it, and the planner's own limit applies", async () => {
    const board = sample();
    const elective = todo(board, "major_elective").find((c) => c.valid_sessions.length > 0)!;
    const spy = show(board, jsonResponse({ ok: false, error: "Major electives requirement would be exceeded (18 of 18 credit points already completed, enrolled or planned)." }, { status: 422 }));
    drag(elective.name, elective.valid_sessions[0]!);
    expect(await screen.findByRole("alert")).toHaveTextContent("Major electives requirement would be exceeded");
    expect(JSON.parse(String((spy.mock.calls[0]?.[1] as RequestInit).body))).toEqual({ code: elective.code, to: elective.valid_sessions[0] });
  });
});

describe("dragging near an edge scrolls", () => {
  function overAt(target: Element, props: { clientX?: number; clientY?: number }) {
    const event = Object.assign(new Event("dragover", { bubbles: true, cancelable: true }), { dataTransfer: dataTransfer(), clientX: 0, clientY: 0, ...props });
    fireEvent(target, event);
  }
  const rect = (r: Partial<DOMRect>) => () => ({ left: 0, right: 0, top: 0, bottom: 0, width: 0, height: 0, x: 0, y: 0, toJSON: () => ({}), ...r }) as DOMRect;

  it("scrolls the sessions sideways near the right and left edges while a card is being dragged", () => {
    const { container } = render(<BoardView initial={failed()} moveEndpoint="/m" csrf="t" />);
    const box = container.querySelector(".board-scroll") as HTMLElement;
    box.getBoundingClientRect = rect({ left: 0, right: 1000, width: 1000 });
    box.scrollLeft = 300;
    fireEvent.dragStart(screen.getByText("Programming 2").closest("li") as HTMLElement, { dataTransfer: dataTransfer() });
    overAt(column("Spring 2027"), { clientX: 995 });
    expect(box.scrollLeft).toBeGreaterThan(300);
    const after = box.scrollLeft;
    overAt(column("Spring 2027"), { clientX: 5 });
    expect(box.scrollLeft).toBeLessThan(after);
  });

  it("scrolls the list under the pointer near its top and bottom", () => {
    const { container } = render(<BoardView initial={parseBoard(boardRaw("fresh"))} moveEndpoint="/m" csrf="t" />);
    const list = column("To place").querySelector(".board-cards") as HTMLElement;
    list.getBoundingClientRect = rect({ top: 100, bottom: 600, height: 500 });
    list.scrollTop = 200;
    fireEvent.dragStart(container.querySelector(".board-card-todo") as HTMLElement, { dataTransfer: dataTransfer() });
    overAt(column("To place"), { clientY: 598 });
    expect(list.scrollTop).toBeGreaterThan(200);
    const after = list.scrollTop;
    overAt(column("To place"), { clientY: 102 });
    expect(list.scrollTop).toBeLessThan(after);
  });

  it("does nothing in the middle, or when nothing is being dragged", () => {
    const { container } = render(<BoardView initial={failed()} moveEndpoint="/m" csrf="t" />);
    const box = container.querySelector(".board-scroll") as HTMLElement;
    box.getBoundingClientRect = rect({ left: 0, right: 1000, width: 1000 });
    box.scrollLeft = 300;
    overAt(column("Spring 2027"), { clientX: 995 }); // no drag in progress
    expect(box.scrollLeft).toBe(300);
    fireEvent.dragStart(screen.getByText("Programming 2").closest("li") as HTMLElement, { dataTransfer: dataTransfer() });
    overAt(column("Spring 2027"), { clientX: 500 });
    expect(box.scrollLeft).toBe(300);
  });
});
