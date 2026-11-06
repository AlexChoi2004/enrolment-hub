// End-to-end smoke check: the REAL Flask server, the REAL built bundle, a simulated browser (jsdom).
// Usage: node frontend/smoke.mjs http://127.0.0.1:5055 [preset-name-for-the-report]
import { readFileSync } from "node:fs";
import { CookieJar, JSDOM } from "jsdom";

const base = process.argv[2] ?? "http://127.0.0.1:5055";
const jar = new CookieJar();
const cookieHeader = (url) => jar.getCookieStringSync(url);
async function request(path, init = {}) {
  const url = new URL(path, base).href;
  const response = await fetch(url, { redirect: "manual", ...init, headers: { ...(init.headers ?? {}), Cookie: cookieHeader(url) } });
  for (const c of response.headers.getSetCookie()) jar.setCookieSync(c, url);
  return response;
}

// log in as the demo student
const loginPage = await (await request("/login")).text();
const csrf = /name="csrf_token" value="([^"]+)"/.exec(loginPage)?.[1];
const body = new URLSearchParams({ csrf_token: csrf, email: "john.doe@student.uni.edu.au", password: "Johndoe#1" });
const login = await request("/login", { method: "POST", body, headers: { "Content-Type": "application/x-www-form-urlencoded" } });
if (login.status !== 302) throw new Error(`login failed: ${login.status}`);

// the page the student lands on
const html = await (await request("/dashboard")).text();
const bundle = readFileSync(new URL("../shared/static/dist/dashboard.js", import.meta.url), "utf8").replace(/;?export\s*\{[^}]*\};?\s*$/, "");
const dom = new JSDOM(html, {
  url: `${base}/dashboard`, runScripts: "outside-only", pretendToBeVisual: true,
  beforeParse(window) {
    window.fetch = async (input, init) => request(new URL(input, base).pathname, { headers: init?.headers ?? {} });
  },
});
const { window } = dom;
const before = window.document.querySelector("#dashboard-root").textContent.trim().slice(0, 60);
window.eval(bundle); // what the browser does with <script type="module" src="/static/dist/dashboard.js">
const waitFor = async (fn, ms = 4000) => { const end = Date.now() + ms; while (Date.now() < end) { const v = fn(); if (v) return v; await new Promise((r) => setTimeout(r, 50)); } return null; };
const hello = await waitFor(() => window.document.querySelector(".dash-hello"));
if (!hello) throw new Error("the dashboard never rendered: " + window.document.querySelector("#dashboard-root").innerHTML.slice(0, 300));
const q = (s) => [...window.document.querySelectorAll(s)];
console.log("before React:", JSON.stringify(before));
console.log("heading:     ", hello.textContent);
console.log("bars:        ", q('[role="progressbar"]').length, "| stat cards:", q(".dash-stat").length, "| requirements:", q(".dash-req").length, "| steps:", q(".dash-step a").length);
console.log("graduation:  ", window.document.querySelector(".dash-grad-session")?.textContent);
console.log("first bar:   ", q('[role="progressbar"]')[0]?.getAttribute("aria-valuetext"));
console.log("step links:  ", q(".dash-step a").map((a) => a.getAttribute("href")).join(", "));
console.log("scripts in page:", q("script").map((s) => s.getAttribute("src") ?? "INLINE").join(", "));

// ---- the planner board: the real page, the real bundle and the real plan; then a real drag-and-drop move through the real server
async function openBoard() {
  const boardHtml = await (await request("/planner/board")).text();
  const boardBundle = readFileSync(new URL("../shared/static/dist/board.js", import.meta.url), "utf8").replace(/;?export\s*\{[^}]*\};?\s*$/, "");
  const page = new JSDOM(boardHtml, {
    url: `${base}/planner/board`, runScripts: "outside-only", pretendToBeVisual: true,
    beforeParse(w) { w.fetch = async (input, init) => request(new URL(input, base).pathname, { method: init?.method ?? "GET", headers: init?.headers ?? {}, body: init?.body }); },
  });
  page.window.eval(boardBundle);
  const ready = await waitFor(() => page.window.document.querySelector(".board-col"));
  if (!ready) throw new Error("the board never rendered: " + page.window.document.querySelector("#board-root").innerHTML.slice(0, 300));
  return page.window;
}
const boardWindow = await openBoard();
const cols = [...boardWindow.document.querySelectorAll(".board-col")];
console.log("board:       ", cols.length, "columns |", cols.map((c) => c.getAttribute("aria-label")).slice(0, 3).join(", "), "...");
if (cols.length !== 11) throw new Error(`expected a to-place column and ten sessions, saw ${cols.length}`);

// drag a real subject onto a real session, using the page's own events
const card = [...boardWindow.document.querySelectorAll(".board-card")].find((li) => li.textContent.includes("Communication for IT Professionals"));
const target = cols.find((c) => c.getAttribute("aria-label") === "Spring 2027");
if (!card || !target) throw new Error("could not find a card to drag");
const dt = { data: {}, setData(k, v) { this.data[k] = v; }, getData(k) { return this.data[k] ?? ""; }, effectAllowed: "", dropEffect: "" };
const fire = (el, type) => { const e = new boardWindow.Event(type, { bubbles: true, cancelable: true }); e.dataTransfer = dt; el.dispatchEvent(e); };
fire(card, "dragstart"); fire(target, "dragover"); fire(target, "drop");
const moved = await waitFor(() => boardWindow.document.querySelector(".board-announce-ok, .board-announce-refused, .board-announce-error"));
if (!moved) throw new Error("the drop got no answer from the server");
console.log("after drop:  ", moved.className.replace("board-announce ", ""), "|", moved.textContent.trim());
if (!moved.classList.contains("board-announce-ok")) throw new Error("the move should have been accepted by the planner");
// the server really changed the plan: a fresh load of the board shows the card in Spring 2027
const again = await openBoard();
const inSpring = [...again.document.querySelectorAll(".board-col")].find((c) => c.getAttribute("aria-label") === "Spring 2027");
if (!inSpring.textContent.includes("Communication for IT Professionals")) throw new Error("the move was not saved");
console.log("reloaded:    ", "Communication for IT Professionals is now in Spring 2027");
