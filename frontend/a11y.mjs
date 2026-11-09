// Accessibility audit: axe-core (the engine behind Lighthouse's accessibility score) against every real page and both React islands,
// using the REAL server and the REAL built bundles in a simulated browser (jsdom).
// Usage: node frontend/a11y.mjs http://127.0.0.1:5055
// jsdom has no layout engine, so rules that need real rendering (colour contrast, target size, scrolling regions) cannot run here:
// colour contrast is covered by tests/shared/test_theme.py, and the manual checks are listed in docs/ACCESSIBILITY.md.
import { readFileSync } from "node:fs";
import { CookieJar, JSDOM } from "jsdom";

const base = process.argv[2] ?? "http://127.0.0.1:5055";
const axeSource = readFileSync(new URL("./node_modules/axe-core/axe.min.js", import.meta.url), "utf8");
const bundle = (name) => readFileSync(new URL(`../shared/static/dist/${name}.js`, import.meta.url), "utf8").replace(/;?export\s*\{[^}]*\};?\s*$/, "");

let jar = new CookieJar();
async function request(path, init = {}) {
  const url = new URL(path, base).href;
  const response = await fetch(url, { redirect: "manual", ...init, headers: { ...(init.headers ?? {}), Cookie: jar.getCookieStringSync(url) } });
  for (const c of response.headers.getSetCookie()) jar.setCookieSync(c, url);
  return response;
}
async function logIn() {
  const page = await (await request("/login")).text();
  const csrf = /name="csrf_token" value="([^"]+)"/.exec(page)?.[1];
  const body = new URLSearchParams({ csrf_token: csrf, email: "john.doe@student.uni.edu.au", password: "Johndoe#1" });
  const res = await request("/login", { method: "POST", body, headers: { "Content-Type": "application/x-www-form-urlencoded" } });
  if (res.status !== 302) throw new Error(`login failed (${res.status})`);
}
const waitFor = async (fn, ms = 5000) => { const end = Date.now() + ms; while (Date.now() < end) { const v = fn(); if (v) return v; await new Promise((r) => setTimeout(r, 50)); } return null; };
const firstLink = (html, pattern) => new RegExp(`href="(${pattern})"`).exec(html)?.[1];

const RULES = {
  runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"] },
  // these need a real layout engine; they are covered by other tests (see the header)
  rules: { "color-contrast": { enabled: false }, "color-contrast-enhanced": { enabled: false }, "scrollable-region-focusable": { enabled: false }, "target-size": { enabled: false } },
};

async function auditHtml(name, path, html, island) {
  const dom = new JSDOM(html, {
    url: new URL(path, base).href, runScripts: "outside-only", pretendToBeVisual: true,
    beforeParse(w) { w.fetch = async (input, init) => request(new URL(input, base).pathname, { method: init?.method ?? "GET", headers: init?.headers ?? {}, body: init?.body }); },
  });
  const { window } = dom;
  if (island) {
    window.eval(bundle(island.bundle));
    if (!(await waitFor(() => window.document.querySelector(island.ready)))) throw new Error(`${name}: the island never rendered`);
  }
  window.eval(axeSource);
  const results = await window.axe.run(window.document, RULES);
  return { name, path, violations: results.violations, incomplete: results.incomplete.length, incompleteIds: results.incomplete.map((i) => i.id), incompleteDetail: results.incomplete, passes: results.passes.length };
}

async function audit(name, path, island) {
  let response = await request(path);
  for (let hops = 0; [301, 302, 303, 307].includes(response.status) && hops < 3; hops++) {  // for example /students/me goes to the student's own record
    path = new URL(response.headers.get("location"), base).pathname;
    response = await request(path);
  }
  if (response.status !== 200) throw new Error(`${name}: ${path} answered ${response.status}`);
  return auditHtml(name, path, await response.text(), island);
}

/** The values a person would send if they pressed the form's button without changing anything. */
function defaultsOf(form) {
  const body = new URLSearchParams();
  for (const el of form.elements) {
    if (!el.name || el.disabled) continue;
    if (el.tagName === "SELECT") body.append(el.name, el.value || el.options[0]?.value || "");
    else if (el.type === "checkbox" || el.type === "radio") { if (el.checked) body.append(el.name, el.value || "on"); }
    else if (el.type !== "submit" && el.type !== "button") body.append(el.name, el.value);
  }
  return body;
}

const results = [];
// logged-out pages first
for (const [name, path] of [["Welcome", "/"], ["Log in", "/login"], ["Register", "/register"], ["Help", "/help"]]) results.push(await audit(name, path));
await logIn();
const subjects = await (await request("/subjects")).text();
const major = firstLink(await (await request("/major")).text(), "/major/[A-Z0-9]+");
const submajor = firstLink(await (await request("/submajor")).text(), "/submajor/[A-Z0-9]+");
const detail = firstLink(subjects, "/subjects/\\d+");
const pages = [
  ["Dashboard (React)", "/dashboard", { bundle: "dashboard", ready: ".dash-hello" }],
  ["Subjects", "/subjects"], ["Subject detail", detail], ["Degree planner", "/planner"],
  ["Planner board (React)", "/planner/board", { bundle: "board", ready: ".board-col" }],
  ["Timetable", "/timetable"], ["My record", "/students/me"], ["Results", "/transcript"],
  ["Choose a major", "/major"], ["Fit for my progress: majors", "/major/fit"], ["Compare two majors", "/major/compare?a=MAJ02900&b=MAJ03445"],
  ["Major swap", major], ["Major: About tab", `${major}?tab=about`],
  ["Choose a sub-major", "/submajor"], ["Fit for my progress: sub-majors", "/submajor/fit"], ["Compare two sub-majors", "/submajor/compare?a=SMJ10167&b=SMJ10166"],
  ["Sub-major swap", submajor], ["Sub-major: About tab", `${submajor}?tab=about`], ["Electives", "/submajor/electives"],
  ["Major: Subjects tab", major], ["Humanitarian Engineering (stream)", "/submajor/SMJ10196"], ["Transdisciplinary elective subject", "/subjects/95003"],
  ["Profile", "/profile"], ["Simulator: reset", "/simulator/reset"],
];
for (const [name, path, island] of pages) {
  if (!path) throw new Error(`could not find a link for ${name}`);
  results.push(await audit(name, path, island));
}

// the simulator: enter results, review them, finish the semester, then the roll-back page exists
const resultsHtml = await (await request("/simulator/results")).text();
results.push(await auditHtml("Simulator: results", "/simulator/results", resultsHtml));
const resultsDom = new JSDOM(resultsHtml);
const form = resultsDom.window.document.querySelector('form[action$="/simulator/review"]');
if (!form) throw new Error("the simulator results form was not found");
const reviewHtml = await (await request("/simulator/review", { method: "POST", body: defaultsOf(form), headers: { "Content-Type": "application/x-www-form-urlencoded" } })).text();
results.push(await auditHtml("Simulator: review", "/simulator/review", reviewHtml));
const finishForm = new JSDOM(reviewHtml).window.document.querySelector('form[action$="/simulator/finish"]');
if (finishForm) await request("/simulator/finish", { method: "POST", body: defaultsOf(finishForm), headers: { "Content-Type": "application/x-www-form-urlencoded" } });
results.push(await audit("Simulator: roll back", "/simulator/rollback"));

let total = 0;
console.log("\nPage".padEnd(30), "violations", " rules passed", " needs review");
for (const r of results) {
  total += r.violations.length;
  console.log(r.name.padEnd(29), String(r.violations.length).padStart(10), String(r.passes).padStart(13), String(r.incomplete).padStart(13));
}
for (const r of results) {
  for (const v of r.violations) {
    console.log(`\n[${v.impact}] ${r.name} (${r.path}): ${v.id} - ${v.help}`);
    for (const n of v.nodes.slice(0, 3)) console.log("    ", n.target.join(" "), "|", n.html.replace(/\s+/g, " ").slice(0, 140));
    if (v.nodes.length > 3) console.log(`     ... and ${v.nodes.length - 3} more`);
  }
}
if (process.env.A11Y_REVIEW) {  // print the items axe could not decide, with their elements
  for (const r of results) for (const i of r.incompleteDetail) if (!["landmark-one-main", "page-has-heading-one"].includes(i.id)) {
    console.log(`\n[needs review] ${r.name} (${r.path}): ${i.id} - ${i.help}`);
    for (const n of i.nodes.slice(0, 3)) console.log("    ", n.target.join(" "), "|", n.html.replace(/\s+/g, " ").slice(0, 140), "|", (n.any[0]?.message ?? n.none[0]?.message ?? "").slice(0, 120));
  }
}
const review = new Map();
for (const r of results) for (const id of r.incompleteIds) review.set(id, (review.get(id) ?? 0) + 1);
console.log("\nAxe could not decide these on its own (a person checks them; see docs/ACCESSIBILITY.md):", [...review].map(([id, n]) => `${id} (${n} pages)`).join(", ") || "none");
console.log(`\n${results.length} pages audited, ${total} violation${total === 1 ? "" : "s"} (axe-core ${JSON.parse(readFileSync(new URL("./node_modules/axe-core/package.json", import.meta.url), "utf8")).version}, WCAG 2.0/2.1/2.2 A and AA plus best practice).`);
process.exit(total === 0 ? 0 : 1);
