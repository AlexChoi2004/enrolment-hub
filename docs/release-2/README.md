# Release 2: the multi-agent swap advisor

- **Scope:** on a swap page, **Explain this swap** runs three roles: an Analyst (code) gets the facts and the verdict, an Advisor (the AI)
  gives a recommendation and things to weigh, and a Checker (code) rejects advice that does not match the facts. The student always makes
  the decision, with a confirmation the server enforces; the AI cannot make the swap.
- **Run instructions:** turn AI mode on, open a major, sub-major or electives swap page and press **Explain this swap**. The
  "Late in the major" starting point (Reset in the bar under the header) gives a "Think carefully" example.
- **Evidence:** the evidence log entries for the swap advisor, and tests covering each way the Checker rejects advice, that nothing is
  ever changed by asking, and the confirmation gate on all three swap pages.
- **Known issues:** it uses one model role by design (the Analyst and Checker are code, so they can be tested); wording varies with the model.
