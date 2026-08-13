# Tool Registry

One-line description of each tool available in the ZoTok Copilot.
Internal agent-graph nodes are listed under `agent_internal` so the
tool-selection judge can score them instead of flagging them as phantom tools.

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
| `spawn_filter_agent` | agent_orchestration | ✅ | Spawn a sub-agent for complex multi-step filtering or cross-referencing tasks. |
| `get_sheet_data` | spreadsheet_read | ✅ | Fetch data from a named spreadsheet/sheet — rows/columns by reference or filter. |
| `list_spreadsheets` | spreadsheet_read | ✅ | List available spreadsheets in the workspace. |
| `search_agent` | agent_orchestration | ✅ | Delegate retrieval to the search sub-agent (spans channels/sheets). |
| `think` | agent_internal | ✅ | Internal reasoning step (no external call) — planner node of the agent graph. |
| `write_todos` | agent_internal | ✅ | Write/update the agent's todo list for the current task. |
| `column_selector` | agent_internal | ✅ | Select relevant columns for a data extraction/formatting task. |
| `format_node` | agent_internal | ✅ | Format the final response into the output schema/message. |
| `search_tools_condition` | agent_internal | ✅ | Route the query to the appropriate search tool (condition node). |
| `compress_node` | agent_internal | ✅ | Compress/trim conversation context for the model window. |

**Last updated:** August 13, 2026 (added spreadsheet tools + agent_internal nodes; traced set from seller-copilot-agent).
