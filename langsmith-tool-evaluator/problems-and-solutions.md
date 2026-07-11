# Problems & Solutions (Analysis)

*Generated: 2026-07-09. Updated: 2026-07-11 with Run v1 findings.*

This document captures architectural gaps in the current tool-selection evaluator and potential approaches to fix them.

---

## Run v1 Findings (July 11, 2026)

### Confirmed Issues from Live API Testing

1. **No phantom tools detected** — all 6 tools called in v1 are in the registry. The `get_invoice_data` phantom tool from the HAR capture was NOT called in this run. The 3 conversation_read tools (search_messages, get_thread_messages, get_channel_data) were never called.

2. **10/50 queries called NO tool** — the copilot answered 20% of queries without any data lookup. These queries are in categories: Reports & Analytics (1), Outstanding & Payments (1), Ledger (1), Orders & Invoices (4), Products & Items (3). This may indicate the copilot is falling back to generic responses for queries it should be querying data for.

3. **Ledger category is 6-8x slower** — avg 84.9s vs 7-12s for all other categories. Query #24 timed out at 306.6s. This is a backend performance issue, not a tool-selection issue.

4. **Query #28 returned empty response** — 0 chars, no error, 58s elapsed. The copilot silently returned nothing. A real user would see a blank response with no explanation.

5. **get_product_analytics responses suspiciously short** (67-88 chars) — likely returning error messages like "No data found" instead of actual analytics. Worth investigating the tool output (not visible in SSE).

6. **3 tools never used** — search_messages, get_thread_messages, get_channel_data were not called by any query. Either the test suite doesn't cover conversation-search use cases, or the copilot's routing doesn't consider these tools.

---



This document captures architectural gaps in the current tool-selection evaluator and potential approaches to fix them. Nothing here is implemented yet — this is a thinking document.

---

## Problem 1: Multi-Turn Conversation Context Is Ignored

### Current Behaviour

Every LangSmith run is evaluated **in isolation**. The prompt sent to the LLM judge contains only:

```
{{USER_QUERY}}            ← this turn's query only
{{SELECTED_TOOL}}         ← the tool the agent picked for this turn
{{SELECTED_TOOL_ARGS}}    ← args for this turn
```

No conversation history, no prior tool results, no `trace_id` grouping.

### Why It Matters

A tool choice that looks wrong in isolation may be completely correct given the preceding conversation. Example:

```
Turn 1 — User: "Show me top customers by outstanding"
          Agent: getCustomerAnalytics → returns [Customer A: ₹50K, Customer B: ₹30K]

Turn 2 — User: "Give me the full ledger for Customer A"
          Agent: getCustomerAccountData → returns detailed entries
```

Evaluating Turn 2 in a vacuum:
- The judge sees "Give me the full ledger for Customer A", which reasonably maps to `getCustomerAccountData`.
- But the judge cannot assess whether the agent **already knew** Customer A was the top customer and correctly followed up, or whether this is a disconnected new request.

Worse, some turns **start entirely new sub-flows** within the same conversation:

```
Turn 1 — "What's the outstanding for Customer X?"
Turn 2 — "Also search for product ABC"
```

Turn 2 is an independent request — the tool choice for Turn 2 has nothing to do with Turn 1. The current evaluator handles this *by accident* (it ignores context), but it also can't tell the difference between:
- ✅ A legitimate new flow start
- ❌ A tool call that makes no sense given the prior conversation

### Potential Solutions

**Approach A: Trace-ID grouping + contextual prompt**

1. Fetch all runs grouped by `trace_id` (or `thread_id` / `langfuse_session_id`).
2. Reconstruct the full (query → tool-call → result) sequence for each conversation.
3. Feed the judge the **preceding 1–3 turns** as context alongside the current turn's query.
4. The judge evaluates: "Given this conversation history, does this tool choice make sense?"

Trade-offs:
- + More accurate evaluation for follow-up turns
- + Can detect redundant tool calls, missed steps, contradictory choices
- - More LLM tokens per evaluation (context window heavier)
- - Requires grouping logic before the eval loop
- - Edge cases: very long conversations, branching tool calls (parallel tool invocations)

**Approach B: Keep isolation but flag "context-dependent" runs**

1. Keep the current per-run evaluation as-is.
2. Add a second pass that groups by `trace_id` and flags runs where the tool choice seems context-dependent.
3. Report counts of context-dependent runs in the summary (without re-evaluating).

Trade-offs:
- + Minimal changes to the current architecture
- + Good enough for aggregate metrics
- - Never fixes the per-run accuracy issue

---

## Problem 2: Phantom Tools — Agent Calls Tools Not in the Registry

### Current Behaviour

The judge always receives the agent's `{{SELECTED_TOOL}}` — whatever name the agent called — and is instructed to:

> "Base your evaluation ONLY on the tool descriptions in the registry above."

If the agent calls a tool that **does not exist** in the registry (e.g. `get_weather_data`), the judge:
1. Reads the registry, finds no matching tool
2. Per Step 5: "If no tool fits, output 'none' as expected_tool"
3. Assigns a score (likely 0.00) with a reason like "agent selected wrong tool"

### Why It Matters

This conflates **two distinct failure modes** into a single bucket:

| Category | What happened | Root cause |
|---|---|---|
| **Wrong tool (Registry)** | Agent picked a known tool but it was the wrong one for the query | Poor reasoning / routing logic |
| **Phantom tool (Unknown)** | Agent called a tool name that doesn't exist in the registry at all | Tool grounding failure / hallucination / stale system prompt |

If 80% of your low scores are from phantom tools, that signals a **system prompt / tool definition issue** — not a reasoning issue. The fix for each category is completely different, but the current metrics treat them identically.

Additionally, sending phantom-tool runs to the LLM judge wastes API calls on cases that don't need reasoning to diagnose.

### Potential Solutions

**Approach A: Pre-filter against registry**

1. After parsing the run, check if `selected_tool` exists in the parsed registry entries (case-sensitive or fuzzy match).
2. If **not found** → auto-categorise as `"phantom_tool"`, assign score `0.00`, skip the LLM call entirely.
3. If **found** → proceed with the normal LLM judge flow.
4. Track phantom count in the summary alongside succeeded/failed/skipped.

Trade-offs:
- + Zero LLM cost for phantom tools
- + Clean metric: "X phantom tools called — review system prompt"
- + Does not confuse the judge with a tool name it cannot reason about
- - Need a fuzzy threshold: "search_product" vs "search_products" — should that match?

**Approach B: Flag phantom tools in judge prompt**

1. Keep the LLM call but add a "tool_is_registered: true/false" field to the judge's output schema.
2. The judge explicitly says whether the selected tool exists in the registry.
3. Aggregate separately in the summary.

Trade-offs:
- + Still uses the LLM (adds cost but keeps all logic in one place)
- - The judge might hallucinate a tool match that doesn't exist
- - Less clean than pre-filter

---

## Problem 3: (Derived) — Aggregate Metrics Lose Signal

Because of problems 1 and 2, the current summary output:

```
Total runs seen:   100
Evaluated:          80
Failed:              5
Skipped:            15
```

...doesn't tell you what to fix. A breakdown like this would be far more actionable:

```
Total runs seen:        100
Evaluated (LLM):         75
├─ Correct (score=1.00):  45
├─ Wrong (known tool):    20
├─ Wrong (phantom tool):  10
Skipped (no query):       15
Failed (API error):       10
Context-dependent:         ?  (requires problem-1 fix)
```

---

## Future Directions (Not Yet Prioritised)

### Multi-turn Context

- **Short term**: Add a `--group-by-trace` flag that enables trace-ID grouping and prints per-conversation stats without changing the evaluator logic.
- **Medium term**: Expand the judge prompt to include `{{CONVERSATION_HISTORY}}` (last N turns as formatted text).
- **Long term**: Evaluate tool **sequences** — not just individual calls — for correctness of overall flow.

### Phantom Tool Detection

- **Short term**: Pre-filter against registry, auto-score 0.00 + new "phantom" bucket.
- **Medium term**: Add a configurable similarity threshold for fuzzy tool-name matching (e.g. `search_product` matches `search_products`).
- **Long term**: Log the phantom tool names to a separate file for system-prompt auditing.
