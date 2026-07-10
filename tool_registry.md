\# Tool Registry



One-line description of each tool defined in \[tool\_registry.json](tool\_registry.json).



| Tool | Family | Enabled | Description |

| --- | --- | --- | --- |

| `search\_threads` | conversation\_read | ✅ | Search conversation threads by topic, category, or time range to find what was discussed or who was contacted. |

| `search\_messages` | conversation\_read | ✅ | Search individual WhatsApp message content across all threads for a specific value/id/phrase. |

| `get\_thread\_messages` | conversation\_read | ✅ | Fetch all messages from a specific channel or thread with no topic filter (full channel dump). |

| `get\_channel\_data` | conversation\_read | ✅ | Look up channel metadata (channelId, workspaceId, description) by channel name. |



| `search\_customers\_master` | customer\_master | ✅ | Resolve customers by name, mobile number, or code for identity resolution. |

| `getCustomerAnalytics` | customer\_analytics | ✅ | Fetch customer outstanding + ageing analytics, bucketed by age (0-30/31-60/>60 days). |



| `getCustomerAccountData` | customer\_finance | ✅ | Fetch detailed ledger entries (invoices, payments, debit/credit, balance history) for one known customer. |



| `search\_product\_master` | product\_master | ✅ | Search the product catalog by name, SKU code, or filters to resolve product IDs and SKU codes. |

| `get\_product\_analytics` | product\_analytics | ✅ | Fetch product performance and inventory metrics (revenue, units sold, stock) grouped by product/category/sku/etc. |

&#x20;

