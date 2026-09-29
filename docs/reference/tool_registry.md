# Tool Registry

One-line description of each tool available in the ZoTok Copilot.

| Tool | Family | Enabled | Description |
| --- | --- | --- | --- |
| `search_threads` | conversation_read | ✅ | Search conversation threads by topic, category, or time range to find what was discussed or who was contacted. |
| `search_messages` | conversation_read | ✅ | Search individual WhatsApp message content across all threads for a specific value/id/phrase. |
| `get_thread_messages` | conversation_read | ✅ | Fetch all messages from a specific channel or thread with no topic filter (full channel dump). |
| `get_channel_data` | conversation_read | ✅ | Look up channel metadata (channelId, workspaceId, description) by channel name. |
| `search_customers_master` | customer_master | ✅ | Resolve customers by name, mobile number, or code for identity resolution. |
| `getCustomerAnalytics` | customer_analytics | ✅ | Fetch customer outstanding + ageing analytics, bucketed by age (0-30/31-60/>60 days). |
| `getCustomerAccountData` | customer_finance | ✅ | Fetch detailed ledger entries (invoices, payments, debit/credit, balance history) for one known customer. |
| `search_product_master` | product_master | ✅ | Search the product catalog by name, SKU code, or filters to resolve product IDs and SKU codes. |
| `get_product_analytics` | product_analytics | ✅ | Fetch product performance and inventory metrics (revenue, units sold, stock) grouped by product/category/sku/etc. |
| `get_sales` | sales_analytics | ✅ | Fetch sales performance data — ranked lists of top customers/products by sales amount, with date ranges. |
| `spawn\_filter\_agent` | agent\_orchestration | ✅ | Spawn a sub-agent for complex multi-step filtering or cross-referencing tasks. |
| `get\_sheet\_data` | spreadsheet\_read | ✅ | Fetch data from a named spreadsheet/sheet — rows/columns by reference or filter. |
| `list\_spreadsheets` | spreadsheet\_read | ✅ | List available spreadsheets in the workspace. |
| `search\_agent` | agent\_orchestration | ✅ | Delegate retrieval to the search sub-agent (spans channels/sheets). |
| `think` | agent\_internal | ✅ | Internal reasoning step (no external call) — planner node of the agent graph. |
| `write\_todos` | agent\_internal | ✅ | Write/update the agent's todo list for the current task. |
| `column\_selector` | agent\_internal | ✅ | Select relevant columns for a data extraction/formatting task. |
| `format\_node` | agent\_internal | ✅ | Format the final response into the output schema/message. |
| `search\_tools\_condition` | agent\_internal | ✅ | Route the query to the appropriate search tool (condition node). |
| `compress\_node` | agent\_internal | ✅ | Compress/trim conversation context for the model window. |

## Usage Across Runs (v1–v4)

| Tool | v1 | v2 | v3 | v4 | Total | Notes |
|------|----|----|----|----|-------|-------|
| getCustomerAnalytics | 15 | — | — | 27 | — | Most used tool across all runs |
| get_sales | 0 | 0 | 0 | 23 | 23 | **New in v4** — 2nd most used immediately |
| getCustomerAccountData | 9 | — | — | 14 | — | Ledger queries |
| get_product_analytics | 11 | — | — | 12 | — | Product queries |
| search_customers_master | 13 | — | — | 4 | — | Dropped significantly in v4 |
| spawn_filter_agent | 0 | 0 | 1 | 1 | 2 | **New in v3** — rarely triggered |
| search_threads | 1 | — | — | 1 | — | Rarely used |
| search_messages | 0 | 0 | 0 | 0 | 0 | **Never used** across all runs |
| get_thread_messages | 0 | 0 | 0 | 0 | 0 | **Never used** across all runs |
| get_channel_data | 0 | 0 | 0 | 0 | 0 | **Never used** across all runs |
| search_product_master | 0 | 0 | 0 | 0 | 0 | **Never used** across all runs |

**Last updated:** August 7, 2026 (post HiraFoods v1 run)

## Per-Account Tool Capture

The usage table above is from Surana runs (agentic SSE protocol). Tool capture depends on the account's stream protocol:

| Account | Protocol | Tool events in SSE | Tool calls captured |
|---|---|---|---|
| Surana Polycot | agentic (`tool_start`/`tool_done`) | ✅ | 82 in v4 (get_sales=23, getCustomerAnalytics=27, get_product_analytics=12, getCustomerAccountData=14, search_customers_master=4, search_threads=1, spawn_filter_agent=1) |
| Unifoods | chat-style (`todo`/`token`/`ui`) | ❌ — server-side execution | 0 (truthful: tools never surfaced) |
| HiraFoods | chat-style (`todo`/`token`/`ui`) | ❌ — server-side execution | 0 in v1 (80 queries) — `todo` events are plan-step intents, not tool calls |

**Implication**: for chat-style accounts, tool accuracy metric is N/A (shows 0%) until the backend exposes tool events in the SSE stream.
