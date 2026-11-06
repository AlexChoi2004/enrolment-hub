import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { type Dashboard as Data, parseDashboard } from "../contract";
import { fixture, raw } from "../test/helpers";
import { Dashboard } from "./Dashboard";

const show = (data: Data) => render(<Dashboard data={data} />);

describe("the sample student, two years in", () => {
  it("greets them with their period, major and sub-major", () => {
    show(fixture("sample"));
    expect(screen.getByRole("heading", { name: "Welcome back, John" })).toBeInTheDocument();
    expect(screen.getByText("Autumn 2027 · Year 3, Semester 1")).toBeInTheDocument();
    expect(screen.getByText("Enterprise Software Development · Innovation and Entrepreneurship")).toBeInTheDocument();
  });

  it("shows the overall progress as a progress bar a screen reader can read", () => {
    show(fixture("sample"));
    const bar = screen.getByRole("progressbar", { name: "Degree progress" });
    expect(bar).toHaveAttribute("aria-valuetext", "120 of 192 credit points: 96 completed, 24 in progress, 0 planned");
  });

  it("shows the four credit point cards", () => {
    show(fixture("sample"));
    const cards = within(screen.getByRole("list", { name: "Credit points" })).getAllByRole("listitem");
    expect(cards.map((c) => c.textContent)).toEqual([
      "Completed96 cp16 subjects", "In progress24 cp4 subjects", "Planned0 cp0 subjects", "Still to plan72 cpof 192 cp",
    ]);
  });

  it("shows the projected graduation the server worked out", () => {
    show(fixture("sample"));
    const section = screen.getByRole("region", { name: "Projected graduation" });
    expect(section).toHaveTextContent("Spring 2028");
    expect(section).toHaveTextContent("3 more sessions after the current one");
  });

  it("shows a bar for each requirement with its numbers", () => {
    show(fixture("sample"));
    const reqs = within(screen.getByRole("region", { name: "Requirements" })).getAllByRole("listitem");
    expect(reqs).toHaveLength(5);
    expect(screen.getByRole("progressbar", { name: "Sub-major core" })).toHaveAttribute("aria-valuenow", "24");
    expect(reqs[0]).toHaveTextContent("Core subjects60 / 96 cp");
  });

  it("marks the heavy session by its own verdict, in words", () => {
    show(fixture("sample"));
    const session = within(screen.getByRole("region", { name: "Sessions ahead" }));
    expect(session.getByText("Heavy")).toBeInTheDocument();
    expect(session.getByText("Current")).toBeInTheDocument();
    expect(session.getByText(/24 of 24 cp · 4 enrolled subjects, 0 planned/)).toBeInTheDocument();
  });

  it("links the next steps to real pages", () => {
    show(fixture("sample"));
    const steps = within(screen.getByRole("region", { name: "Next steps" })).getAllByRole("link");
    expect(steps.map((a) => a.getAttribute("href"))).toEqual(["/planner", "/planner"]);
  });
});

describe("a first-year student", () => {
  it("is told the major and pathway are not chosen yet, with dashed placeholder requirements", () => {
    show(fixture("fresh"));
    expect(screen.getByText("No major chosen yet · No sub-major or electives chosen yet")).toBeInTheDocument();
    expect(screen.getByText("Major (not chosen yet)").closest("li")).toHaveClass("dash-req-pending");
    expect(screen.getByText("Sub-major or electives (not chosen yet)").closest("li")).toHaveClass("dash-req-pending");
  });

  it("is sent to choose a major first", () => {
    show(fixture("fresh"));
    const links = within(screen.getByRole("region", { name: "Next steps" })).getAllByRole("link");
    expect(links.map((a) => a.getAttribute("href"))).toEqual(["/major", "/submajor", "/subjects"]);
    expect(links[0]).toHaveTextContent("Needs attention: Choose your major");
  });

  it("is projected eight sessions from Autumn 2027", () => {
    show(fixture("fresh"));
    expect(screen.getByRole("region", { name: "Projected graduation" })).toHaveTextContent("Spring 2030");
  });
});

describe("a student with a failed prerequisite", () => {
  it("sees the retake and the blocked subject as things needing attention", () => {
    show(fixture("failed"));
    const steps = within(screen.getByRole("region", { name: "Next steps" })).getAllByRole("listitem");
    expect(steps[0]).toHaveClass("dash-step-warning");
    expect(steps[0]).toHaveTextContent("48024 Programming 2 was failed");
    expect(steps[1]).toHaveTextContent("(failed: retake it first)");
  });
});

describe("a student late in their major", () => {
  it("sees the 'too heavy' verdict on their session", () => {
    show(fixture("late"));
    expect(within(screen.getByRole("region", { name: "Sessions ahead" })).getByText("Too heavy")).toHaveClass("dash-wl-too_heavy");
  });
});

describe("edge cases", () => {
  it("says so when the whole degree is done or in progress", () => {
    const data = parseDashboard({ ...(raw("sample") as object), graduation: { session: "Autumn 2027", sessions_left: 0, remaining_cp: 0, finished: true } });
    show(data);
    expect(screen.getByRole("region", { name: "Projected graduation" })).toHaveTextContent("Everything is done or in progress.");
  });

  it("says the current session is the last one needed", () => {
    const data = parseDashboard({ ...(raw("sample") as object), graduation: { session: "Autumn 2027", sessions_left: 0, remaining_cp: 12, finished: false } });
    show(data);
    expect(screen.getByRole("region", { name: "Projected graduation" })).toHaveTextContent("This is the last session you need");
  });

  it("shows a calm message when there are no next steps", () => {
    show(parseDashboard({ ...(raw("sample") as object), next_steps: [] }));
    expect(screen.getByText("Nothing needs your attention right now.")).toBeInTheDocument();
  });

  it("shows 'not enough information' for a session with no workload verdict", () => {
    const data = raw("sample") as { sessions: { workload: string | null; workload_label: string }[] };
    data.sessions[0] = { ...data.sessions[0]!, workload: null, workload_label: "Not enough information" };
    show(parseDashboard(data));
    expect(screen.getByText("Not enough information")).toHaveClass("dash-wl-unknown");
  });

  it("escapes text instead of treating it as markup", () => {
    const data = raw("sample") as { student: { display_name: string }; next_steps: { text: string }[] };
    data.student.display_name = "<img src=x onerror=alert(1)> Evil";
    data.next_steps[0]!.text = "<b>bold</b> <script>alert(1)</script>";
    const { container } = show(parseDashboard(data));
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
    expect(screen.getByText(/<b>bold<\/b>/)).toBeInTheDocument();
  });
});
