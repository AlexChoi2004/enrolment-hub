import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

// Read the real files from disk: Vitest replaces CSS imports with empty text, which would make these checks pass on nothing.
// (tests are run from the frontend folder, by npm test and in CI)
const read = (path: string) => readFileSync(resolve(process.cwd(), path), "utf8");
const theme = read("../shared/static/theme.css");
const SHEETS = { dashboard: read("src/dashboard.css"), board: read("src/board/board.css") };
const HARD_CODED = /#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(/g;
const COLOUR_WORDS = /(?<![-\w])(white|black|red|green|blue|gray|grey)(?![-\w])/g; // not the 'white' in white-space
const withoutComments = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, "");

describe.each(Object.entries(SHEETS))("the %s styles", (_name, css) => {
  it("are a real file with real content, so the checks below mean something", () => {
    expect(css.length).toBeGreaterThan(1500);
    expect(theme.length).toBeGreaterThan(5000);
    expect(theme).toContain("--accent");
  });

  it("use only the site's colour tokens, so dark mode works", () => {
    expect(withoutComments(css).match(HARD_CODED)).toBeNull();
    expect(withoutComments(css).match(COLOUR_WORDS)).toBeNull();
  });

  it("only use tokens that exist in the theme", () => {
    const used = new Set([...css.matchAll(/var\((--[\w-]+)\)/g)].map((m) => m[1] as string));
    const defined = new Set([...theme.matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1] as string));
    expect(used.size).toBeGreaterThan(8);
    expect([...used].filter((token) => !defined.has(token))).toEqual([]);
  });
});

describe("the colour check", () => {
  it("would notice a hard-coded colour", () => {
    const sample = ".x { color: #fff; background: rgb(0, 0, 0); border-color: red; white-space: nowrap; }";
    expect(sample.match(HARD_CODED)).toHaveLength(2);
    expect(sample.match(COLOUR_WORDS)).toEqual(["red"]);
  });
});
