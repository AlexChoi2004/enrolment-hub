# Accessibility

What was checked, how, what it found, and what no automated tool can decide. The aim is WCAG 2.2 level AA for every page, including the two
React and TypeScript pages (the dashboard and the planner board) and both colour themes.

## What is checked, and where it runs
| Check | How | Runs |
|---|---|---|
| **axe-core 4.14.0**, WCAG 2.0, 2.1 and 2.2 A and AA plus best practice | `frontend/a11y.mjs` loads the real server and the real built bundles in a simulated browser and audits **22 pages**: every page, a subject, a major and a sub-major, and the simulator's whole flow (results, review, roll back). The two React pages are audited after they have rendered. | CI, in the smoke job, on every pull request |
| **Page structure** | `tests/shared/test_accessibility.py`: one `<main>` and one `<h1>`, heading levels that never skip, a name for every link, button, table header and form control, distinct names for the two navigation landmarks, no duplicate ids, a unique title per page, a skip link as the first focusable element, zoom allowed. The checker is itself tested against 18 deliberately broken pages, so a pass means something. | Python tests |
| **Colour contrast** | `tests/shared/test_theme.py`: about 150 WCAG contrast checks (4.5:1 for text, 3:1 for edges) over the colour tokens in **both** themes, including badges, the timetable, load colours and messages. The focus ring is checked at 3:1 against ten surfaces in both themes. | Python tests |
| **Keyboard and motion** | One visible focus ring everywhere (`:focus-visible`), a skip link, and a stylesheet rule that stops all animation for people who ask for reduced motion. On the planner board, every card has a **Move to…** menu that does everything dragging does, and keyboard focus follows the card to its new place. | Python and frontend tests |
| **Messages** | Errors are announced urgently (`role="alert"`), everything else politely (`role="status"`). The board announces every move and every refusal. | Python and frontend tests |

## What the first audit found, and what changed
The first run (before this work) found **26 violations across 22 pages, which were 4 distinct problems**:

| Problem | Where | Fix |
|---|---|---|
| The two navigation bars had no distinct names (moderate) | every page | `aria-label="Main"` and `aria-label="Account"` |
| The simulator's result dropdowns and mark boxes had no accessible name, so a screen reader announced only "combo box" (**critical**) | Simulator results | A real label for each, hidden visually and read by screen readers |
| A heading level was skipped, h1 straight to h3 (moderate) | Subject detail | The headings are h2, and look the same |
| Empty table header cells (minor) | Degree planner, My record | A screen-reader-only "Actions" |

The same audit also marked one item "needs review" that was a genuine problem: a tick mark whose label was on a plain `<span>`, which screen readers do not reliably announce. It now has real text.
Things axe cannot see were fixed too: there was **no skip link** and **no explicit focus style**, so keyboard focus depended on each browser's default; and on the planner board, **keyboard focus was lost after a move**.
After the fixes the audit reports **0 violations on all 22 pages**. Two page-level rules (one main landmark, one level-one heading) are always "needs review" in a simulated browser; the Python structure tests check both on every page instead.

## Design decisions
- **Colour is never the only signal.** Progress bars use solid, lighter and striped fills and name each kind in text; workload and states are words; a locked subject says so.
- **Dragging is never the only way.** Native drag and drop does not work with a keyboard or a touch screen, so every card has a menu, and the classic planner is still there.
- **Refusals explain themselves.** The planner's own reason is shown in an announced message, not only by a card shaking.
- **Motion respects the device setting,** and so does the colour theme (light or dark follows the device by default).
- **Zoom is allowed,** and the layout reflows.
- **Dark mode is measured,** not judged by eye: the contrast numbers are in tests.

## What this does not prove
- The audit runs in a simulated browser with no layout engine, so axe could not check **colour contrast as rendered**, **target sizes** or **scrollable regions**. Contrast is checked from the colour tokens instead; the rendered result and target sizes need a person (below).
- **No screen reader was used by the author.** Automated tools find missing names and bad structure, not whether a page makes sense when read aloud.
- Updates that happen without a page load (the subject filters, the board's announcements) were tested for the right roles, not with real assistive technology.
- Pointer dragging on the board has no keyboard equivalent by itself; the menu is the equivalent.

## Manual checks (to be done with real tools)
| Check | How | Result |
|---|---|---|
| Lighthouse accessibility score | Chrome, DevTools, Lighthouse, Accessibility only. Run on the Dashboard, the Planner board and Subjects, in light and dark. | _fill in_ |
| Keyboard only | Put the mouse aside. Tab through the Dashboard, then use the board's **Move to…** menus to plan a subject; try the skip link. | _fill in_ |
| Zoom and small screens | Browser zoom 200%, and a 320 px wide window: nothing should be cut off or need sideways scrolling, except the board's own sessions. | _fill in_ |
| Screen reader | Five minutes with NVDA or Windows Narrator on the Dashboard and the board: are the headings, progress bars and messages read sensibly? | _fill in_ |

## Re-running
```bash
python -m pytest -q tests/shared                         # structure and contrast, no Node needed
cd frontend && npm ci && cd ..                           # once, then:
python app.py                                            # in one terminal (ALLOW_REGISTRATION=1 to include the sign-up page)
node frontend/a11y.mjs http://127.0.0.1:5000             # in another: prints every violation, exits 1 if there is one
A11Y_REVIEW=1 node frontend/a11y.mjs ...                 # also prints what axe could not decide
```
