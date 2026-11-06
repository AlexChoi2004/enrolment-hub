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
