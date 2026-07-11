# HEART — Key Principles of Eval Testing

*This file is the single source of truth for how eval testing is conducted.
Every rerun must follow these principles. Update this file if principles evolve.*

---

## 1. THINK LIKE A USER, NOT A DEVELOPER

- Send the query, capture what comes back — errors and all.
- DO NOT retry failed queries. If the API returns an error, that IS the result.
  Record it exactly as a user would have experienced it.
- A 500, a timeout, a partial response — these are real user pain points, not
  bugs in the test harness. They need to be visible in eval results so devs
  see what users actually face.
- The only exception: auth token refresh (401). Re-auth silently and continue.
  The user never sees auth internals.

## 2. WAIT PATIENTLY FOR SSE RESPONSES

- Copilot queries are multi-turn, data-driven, and often return large tables.
- SSE stream timeout must be generous — 300s minimum per query.
- The first token may arrive late. The stream may pause between tool_start and
  tool_done while the backend fetches data. This is normal. Do not cut it short.
- If the stream genuinely hangs (no data for 120s), then we time out — but that
  itself is a finding (backend too slow for a real user).

## 3. MEASURE RESPONSE TIME PER QUERY

- Every query result must record `response_time_seconds`.
- This tells us:
  - Which query types are slowest (which features users wait longest for)
  - Whether dev changes improved or worsened latency
  - A baseline for SLA expectations
- Track from the moment POST /stream is sent to the moment `event: done` is
  received.

## 4. SUPPORT VERSIONED RERUNS

- As devs improve the copilot, we will rerun these same queries.
- Each run produces a NEW query_results.jsonl — never overwrite previous runs.
- Output filenames must be versioned: `query_results_v{N}.jsonl` where N
  increments per run. Start counting from 1.
- A `runs/` manifest file tracks: version, timestamp, total queries, success
  count, fail count, avg response time.
- This allows comparing v1 vs v2 vs v3 to measure improvement over time.

## 5. NO RETRY, NO MASKING

- If a query fails, record: the error message, the partial response (if any),
  the tools that were called before failure, the time elapsed before failure.
- Do not mask errors with "retry succeeded" — that hides real problems.
- The eval's job is to surface truth, not to make the copilot look good.

## 6. WHAT WE COLLECT PER QUERY

Each record in query_results:
  - query_index       : 1-based position in the test suite
  - query             : the user query text
  - category          : functional group from Excel
  - remarks           : human annotation from Excel (if any)
  - tool_calls        : list of {tool, input} from tool_start events
  - response          : reconstructed text from token events
  - status_sequence   : ordered phase names from status events
  - suggestions       : follow-up suggestions
  - response_time_seconds : wall-clock time for this query
  - error             : error message if any (user-visible reality)
  - thread_id         : UUID of the thread
  - timestamp         : ISO datetime of this run