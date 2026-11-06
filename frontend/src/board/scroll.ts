/**
 * Auto-scroll while dragging. Browsers only scroll the page itself when you drag near its edge, and not reliably inside nested
 * scrolling areas, so the board does it: near the start or end of an area, scroll it, faster the closer to the edge.
 */
export const EDGE_ZONE = 56; // pixels from an edge where scrolling starts
export const MAX_STEP = 20; // pixels scrolled per drag event at the very edge

/** How far to scroll (negative = towards the start) for a pointer at `position` inside an area from `start` to `end`. */
export function edgeDelta(position: number, start: number, end: number, zone: number = EDGE_ZONE, max: number = MAX_STEP): number {
  if (end - start <= zone * 2) return 0; // too small to have two edges
  if (position < start + zone) return -Math.ceil(max * Math.min(1, (start + zone - position) / zone));
  if (position > end - zone) return Math.ceil(max * Math.min(1, (position - (end - zone)) / zone));
  return 0;
}
