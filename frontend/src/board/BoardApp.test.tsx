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
    expect(column("To place")).toHaveTextContent("17 subjects");
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

  it("reminds students to choose electives in the classic planner", () => {
    show(failed());
    expect(screen.getByText(/Still to choose in the/)).toHaveTextContent("Major electives");
    expect(screen.getByRole("link", { name: "classic planner" })).toHaveAttribute("href", "/planner");
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
