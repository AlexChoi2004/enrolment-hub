/* Dark mode.
   By default the site follows the system or browser setting (the stylesheet does that by itself, with no JavaScript).
   This script adds the toggle: a student's choice is remembered in this browser, and choosing the same as the system
   setting forgets the override, so the site goes back to following it. It runs in <head> so there is no flash of the
   wrong theme. The logic is plain functions, unit-tested with Node (tests/js/theme.test.mjs). */
(function (root) {
  "use strict";
  var KEY = "theme";

  function resolveTheme(stored, systemDark) {
    if (stored === "light" || stored === "dark") return stored;
    return systemDark ? "dark" : "light";
  }

  /* What a click does: switch to the other theme. If that is what the system already says, forget the override. */
  function nextChoice(stored, systemDark) {
    var next = resolveTheme(stored, systemDark) === "dark" ? "light" : "dark";
    var system = systemDark ? "dark" : "light";
    return { theme: next, stored: next === system ? null : next };
  }

  function init(win) {
    var doc = win.document, html = doc.documentElement;
    var query = win.matchMedia ? win.matchMedia("(prefers-color-scheme: dark)") : null;
    function systemDark() { return !!(query && query.matches); }
    function read() {
      try { var v = win.localStorage.getItem(KEY); return v === "light" || v === "dark" ? v : null; } catch (e) { return null; }
    }
    function write(v) {
      try { if (v) win.localStorage.setItem(KEY, v); else win.localStorage.removeItem(KEY); } catch (e) { /* private mode: it just won't be remembered */ }
    }
    function apply(stored) {
      if (stored) html.setAttribute("data-theme", stored); else html.removeAttribute("data-theme");
    }
    function paint() {
      var button = doc.getElementById("theme-toggle");
      if (!button) return;
      var dark = resolveTheme(read(), systemDark()) === "dark";
      button.textContent = "Dark mode: " + (dark ? "On" : "Off");
      button.setAttribute("aria-pressed", dark ? "true" : "false");
    }
    function wire() {
      var button = doc.getElementById("theme-toggle");
      if (!button) return;
      button.hidden = false; // without JavaScript the button stays hidden and the system setting still applies
      button.addEventListener("click", function () {
        var choice = nextChoice(read(), systemDark());
        write(choice.stored);
        apply(choice.stored);
        paint();
      });
      paint();
    }
    apply(read());
    if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", wire); else wire();
    if (query && query.addEventListener) query.addEventListener("change", paint);
  }

  var api = { KEY: KEY, resolveTheme: resolveTheme, nextChoice: nextChoice, init: init };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root && root.document) { init(root); root.EnrolmentTheme = api; }
})(typeof window !== "undefined" ? window : undefined);
