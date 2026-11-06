import { describe, expect, it } from "vitest";
import { cp, firstName, percent, plural, yearAndSemester } from "./format";

describe("percent", () => {
  it("rounds to a whole number", () => {
    expect(percent(1, 3)).toBe(33);
    expect(percent(2, 3)).toBe(67);
    expect(percent(96, 192)).toBe(50);
  });
  it("is 0 when there is nothing to divide by, and never goes outside 0 to 100", () => {
    expect(percent(5, 0)).toBe(0);
    expect(percent(5, -3)).toBe(0);
    expect(percent(300, 192)).toBe(100);
    expect(percent(-4, 10)).toBe(0);
  });
});

describe("words", () => {
  it("pluralises", () => {
    expect(plural(1, "subject")).toBe("1 subject");
    expect(plural(0, "subject")).toBe("0 subjects");
    expect(plural(3, "more session")).toBe("3 more sessions");
    expect(plural(2, "enrolled subject")).toBe("2 enrolled subjects");
    expect(plural(2, "category", "categories")).toBe("2 categories");
  });
  it("formats credit points and the period", () => {
    expect(cp(24)).toBe("24 cp");
    expect(yearAndSemester(3, 1)).toBe("Year 3, Semester 1");
  });
  it("takes the first name", () => {
    expect(firstName("John Doe")).toBe("John");
    expect(firstName("  Mary   Jane Watson ")).toBe("Mary");
    expect(firstName("Cher")).toBe("Cher");
  });
});
