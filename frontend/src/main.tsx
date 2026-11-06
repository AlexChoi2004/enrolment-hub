import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./dashboard.css";

/** Mount the dashboard into the element the Flask page provides. Does nothing on pages that do not have it. */
export function mount(root: HTMLElement | null, fetchImpl?: typeof fetch): void {
  const endpoint = root?.dataset["endpoint"];
  if (!root || !endpoint) return;
  createRoot(root).render(
    <StrictMode>
      <App endpoint={endpoint} {...(fetchImpl ? { fetchImpl } : {})} />
    </StrictMode>,
  );
}

mount(document.getElementById("dashboard-root"));
