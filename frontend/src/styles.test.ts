import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

// Read the real files from disk: Vitest replaces CSS imports with empty text, which would make these checks pass on nothing.
// (tests are run from the frontend folder, by npm test and in CI)
const css = readFileSync(resolve(process.cwd(), "src/dashboard.css"), "utf8");
const theme = readFileSync(resolve(process.cwd(), "../shared/static/theme.css"), "utf8");
const HARD_CODED = /#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(/g;
const COLOUR_WORDS = /(?<![-\w])(white|black|red|green|blue|gray|grey)(?![-\w])/g; // not the 'white' in white-space

describe("the dashboard styles", () => {
  it("are real files with real content, so the checks below mean something", () => {
    expect(css.length).toBeGreaterThan(1500);
    expect(theme.length).toBeGreaterThan(5000);
    expect(css).toContain(".dash-card");
    expect(theme).toContain("--accent");
  });

  it("use only the site's colour tokens, so dark mode works", () => {
    const withoutComments = css.replace(/\/\*[\s\S]*?\*\//g, "");
    expect(withoutComments.match(HARD_CODED)).toBeNull();
    expect(withoutComments.match(COLOUR_WORDS)).toBeNull();
  });

  it("would notice a hard-coded colour", () => {
    const sample = ".x { color: #fff; background: rgb(0, 0, 0); border-color: red; white-space: nowrap; }";
    expect(sample.match(HARD_CODED)).toHaveLength(2);
    expect(sample.match(COLOUR_WORDS)).toEqual(["red"]);
  });

  it("only use tokens that exist in the theme", () => {
    const used = new Set([...css.matchAll(/var\((--[\w-]+)\)/g)].map((m) => m[1] as string));
    const defined = new Set([...theme.matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1] as string));
    expect(used.size).toBeGreaterThan(10);
    expect([...used].filter((token) => !defined.has(token))).toEqual([]);
  });
});
