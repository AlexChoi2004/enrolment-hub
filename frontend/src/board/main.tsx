import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BoardApp } from "./BoardApp";
import "../dashboard.css";
import "./board.css";

/** Mount the board into the element the Flask page provides. Does nothing on pages that do not have it. */
export function mountBoard(root: HTMLElement | null, fetchImpl?: typeof fetch): void {
  const boardEndpoint = root?.dataset["boardEndpoint"];
  const moveEndpoint = root?.dataset["moveEndpoint"];
  const csrf = root?.dataset["csrf"];
  if (!root || !boardEndpoint || !moveEndpoint || !csrf) return;
  createRoot(root).render(
    <StrictMode>
      <BoardApp boardEndpoint={boardEndpoint} moveEndpoint={moveEndpoint} csrf={csrf} {...(fetchImpl ? { fetchImpl } : {})} />
    </StrictMode>,
  );
}

mountBoard(document.getElementById("board-root"));
