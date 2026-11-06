// Run with: node --test tests/js/theme.test.mjs    (also run by tests/shared/test_theme.py when Node is installed)
import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const theme = require("../../shared/static/theme.js");

test("with nothing stored the system setting decides", () => {
  assert.equal(theme.resolveTheme(null, true), "dark");
  assert.equal(theme.resolveTheme(null, false), "light");
  assert.equal(theme.resolveTheme(undefined, true), "dark");
});

test("a stored choice beats the system setting", () => {
  assert.equal(theme.resolveTheme("light", true), "light");
  assert.equal(theme.resolveTheme("dark", false), "dark");
});

test("anything else stored is ignored", () => {
  for (const junk of ["", "blue", "DARK", "null", 1, {}, []]) assert.equal(theme.resolveTheme(junk, false), "light");
});

test("clicking switches to the other theme and remembers it when it differs from the system", () => {
  assert.deepEqual(theme.nextChoice(null, false), { theme: "dark", stored: "dark" });
  assert.deepEqual(theme.nextChoice(null, true), { theme: "light", stored: "light" });
});

test("choosing what the system already says forgets the override", () => {
  assert.deepEqual(theme.nextChoice("dark", false), { theme: "light", stored: null });
  assert.deepEqual(theme.nextChoice("light", true), { theme: "dark", stored: null });
});

function fakeWindow({ stored = null, systemDark = false, storageThrows = false, readyState = "complete" } = {}) {
  const store = new Map(stored ? [["theme", stored]] : []);
  const attrs = new Map();
  const button = { hidden: true, textContent: "Dark mode", attrs: new Map(), handlers: [],
    setAttribute(k, v) { this.attrs.set(k, v); }, addEventListener(type, fn) { this.handlers.push(fn); }, click() { this.handlers.forEach((f) => f()); } };
  const media = { matches: systemDark, listeners: [], addEventListener(type, fn) { this.listeners.push(fn); } };
  const win = {
    document: { readyState, documentElement: { setAttribute: (k, v) => attrs.set(k, v), removeAttribute: (k) => attrs.delete(k) },
      getElementById: (id) => (id === "theme-toggle" ? button : null), addEventListener() {} },
    localStorage: { getItem: (k) => { if (storageThrows) throw new Error("blocked"); return store.has(k) ? store.get(k) : null; },
      setItem: (k, v) => { if (storageThrows) throw new Error("blocked"); store.set(k, v); },
      removeItem: (k) => { if (storageThrows) throw new Error("blocked"); store.delete(k); } },
    matchMedia: () => media,
  };
  return { win, attrs, button, store, media };
}

test("a remembered choice is applied before the page paints", () => {
  const { win, attrs } = fakeWindow({ stored: "dark" });
  theme.init(win);
  assert.equal(attrs.get("data-theme"), "dark");
});

test("with no choice the page is left to the system setting (no attribute)", () => {
  const { win, attrs } = fakeWindow({ systemDark: true });
  theme.init(win);
  assert.equal(attrs.has("data-theme"), false);
});

test("the toggle is shown, labelled, and flips the theme", () => {
  const { win, attrs, button, store } = fakeWindow({ systemDark: false });
  theme.init(win);
  assert.equal(button.hidden, false);
  assert.equal(button.textContent, "Dark mode: Off");
  assert.equal(button.attrs.get("aria-pressed"), "false");
  button.click();
  assert.equal(attrs.get("data-theme"), "dark");
  assert.equal(store.get("theme"), "dark");
  assert.equal(button.textContent, "Dark mode: On");
  assert.equal(button.attrs.get("aria-pressed"), "true");
  button.click();  // back to what the system says: the override is forgotten
  assert.equal(attrs.has("data-theme"), false);
  assert.equal(store.has("theme"), false);
  assert.equal(button.textContent, "Dark mode: Off");
});

test("on a dark system the first click goes light", () => {
  const { win, attrs, button } = fakeWindow({ systemDark: true });
  theme.init(win);
  assert.equal(button.textContent, "Dark mode: On");
  button.click();
  assert.equal(attrs.get("data-theme"), "light");
  assert.equal(button.textContent, "Dark mode: Off");
});

test("when the system changes and nothing is chosen the label follows it", () => {
  const { win, button, media } = fakeWindow({ systemDark: false });
  theme.init(win);
  media.matches = true;
  media.listeners.forEach((f) => f());
  assert.equal(button.textContent, "Dark mode: On");
});

test("blocked storage never breaks the page", () => {
  const { win, attrs, button } = fakeWindow({ storageThrows: true, systemDark: false });
  assert.doesNotThrow(() => theme.init(win));
  assert.doesNotThrow(() => button.click());
  assert.equal(attrs.get("data-theme"), "dark");  // it still switches for this visit; it just cannot be remembered
});

test("it waits for the page before wiring the button if the page is still loading", () => {
  const { win, button } = fakeWindow({ readyState: "loading" });
  theme.init(win);
  assert.equal(button.hidden, true);  // not wired yet: the page has not finished loading
});
