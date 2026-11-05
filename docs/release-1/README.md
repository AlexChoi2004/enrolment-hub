# Release 1: RAG, AI mode and MCP

- **Scope:** cited answers about rules and subjects from the app's own sources (RAG), with "Not enough context" when they do not
  cover a question; AI mode, where a local model answers questions about the signed-in student by calling ten read-only tools; and a
  read-only MCP server that offers the same tools to another AI application. AI mode is off until the student turns it on.
- **Run instructions:** install Ollama, run `ollama pull qwen3:14b`, then turn AI mode on in the top right (see the README). For MCP, see `docs/MCP.md`.
- **Evidence:** the evidence log entries for the AI work, and tests covering the answer checks, prompt-injection attempts, student scoping
  and the MCP server (including a real subprocess and a check that the database file never changes).
- **Known issues:** answers depend on the local model, so wording varies; when a check rejects a written answer the student sees the
  facts or sources instead; the model needs a computer with enough memory to run qwen3:14b.
