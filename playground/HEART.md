# HEART: Playground Eval Principles

## H — Human-Centric
Eval results must be immediately understandable by the delivery team.
Each test case answers: "Is this bot working for the end user right now?"

## E — Engineering Integrity
Every run is versioned and immutable. Results are never overwritten.
The pipeline must be reproducible — same scenarios, same API, same checks.

## A — Actionable
Every failure points to a concrete signal: wrong response type, missing content,
unexpected tool invocation, or API error. No ambiguous pass/fail.

## R — Reliable
The test harness must handle API timeouts, empty responses, and inconsistent
chat state without crashing. A network blip should not invalidate a full run.

## T — Transparent
Dashboard shows raw data alongside aggregated stats. Anyone on the team can
click through from "77% pass rate" to "which query failed and why."
