import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Legend, ProgressBar } from "./ProgressBar";

describe("ProgressBar", () => {
  it("is a progress bar with an accessible name and plain-words value", () => {
    render(<ProgressBar label="Core subjects" total={96} segments={{ completed: 54, enrolled: 6, planned: 12 }} />);
    const bar = screen.getByRole("progressbar", { name: "Core subjects" });
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "96");
    expect(bar).toHaveAttribute("aria-valuenow", "60");
    expect(bar).toHaveAttribute("aria-valuetext", "60 of 96 credit points: 54 completed, 6 in progress, 12 planned");
  });

  it("sizes each part as a share of the total", () => {
    const { container } = render(<ProgressBar label="x" total={100} segments={{ completed: 50, enrolled: 25, planned: 10 }} />);
    const widths = [...container.querySelectorAll<HTMLElement>(".dash-seg")].map((s) => s.style.width);
    expect(widths).toEqual(["50%", "25%", "10%"]);
  });

  it("does not break on an empty or overfull bar", () => {
    const empty = render(<ProgressBar label="empty" total={0} segments={{ completed: 0, enrolled: 0, planned: 0 }} />);
    expect([...empty.container.querySelectorAll<HTMLElement>(".dash-seg")].map((s) => s.style.width)).toEqual(["0%", "0%", "0%"]);
    const full = render(<ProgressBar label="full" total={10} segments={{ completed: 40, enrolled: 0, planned: 0 }} />);
    expect(screen.getByRole("progressbar", { name: "full" })).toHaveAttribute("aria-valuenow", "10");
    expect(full.container.querySelector<HTMLElement>(".dash-seg")?.style.width).toBe("100%");
  });

  it("names its unit for people using a screen reader", () => {
    render(<ProgressBar label="load" total={24} unit="credit points of study" segments={{ completed: 0, enrolled: 18, planned: 0 }} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuetext", expect.stringContaining("18 of 24 credit points of study"));
  });

  it("has a legend that names all three kinds", () => {
    render(<Legend />);
    expect(screen.getByRole("list", { name: "Key" })).toHaveTextContent(/Completed\s+In progress\s+Planned/);
  });
});
