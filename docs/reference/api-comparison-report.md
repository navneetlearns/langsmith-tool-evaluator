# ZoTok Reports API Suite — Chat Tool Comparison

**Date:** 2026-07-17  
**Author:** navneetlearns  
**Purpose:** Compare 5 ZoTok Reports APIs for integration as tool calls behind a conversational chat agent. Determine common data points, unique value, and chat-context richness.

---

## 1. APIs Analyzed

| # | API Endpoint | Domain | Entity | Data Type |
|---|-------------|--------|--------|-----------|
| 1 | `/analytics/sales` | Sales Performance | Customer | Aggregated — ranked list of top customers by sales |
| 2 | `/analytics/customer` | Customer Financial Health | Customer | Aggregated — financial KPIs per customer |
| 3 | `/customer-metrics-report` | Customer Master Data | Customer | Master list — full customer profile with credit, transactions, team |
| 4 | `/analytics/productview` | Product Inventory & Revenue | Product | Aggregated — product-level stock, inventory value, revenue |
| 5 | `/analytics/paymentview` | Payment Receivables & Ageing | Customer | Aggregated — payment ageing/receivables by customer |

---

## 2. Schema Comparison

### 2.1 Sales Analytics (`/analytics/sales`)

**Request:**
```json
{
  "view": "sales",
  "groupBy": ["customerId"],
  "metrics": ["customerFirmName", "totalSales"],
  "fromDate": "2026-07-01",
  "endDate": "2026-07-17",
  "dateColumn": "invoiceDate",
  "limit": 10,
  "offset": 0,
  "sortBy": [{"column": "totalSales", "order": "desc"}]
}
```

**Response fields (confirmed):**
```
data[].sNo               int        — Serial number
data[].customerId        uuid       — Customer identifier
data[].customerFirmName  string     — Customer business name
data[].totalSales        decimal    — Total sales amount
total_count              int        — Total matching records
startRecord              int        — Pagination start
endRecord                int        — Pagination end
```

### 2.2 Customer Analytics (`/analytics/customer`)

**Request:**
```json
{
  "metrics": [
    "totalOrders", "totalOrderValue",
    "totalInvoices", "totalInvoiceValue",
    "pendingInvoices", "pendingInvoiceValue",
    "totalOutstandingValue"
  ],
  "fromDate": "2026-07-12",
  "endDate": "2026-07-17",
  "filters": {}
}
```

**Response:** Unknown (backend error encountered — HIVE_METASTORE_ERROR 429)

### 2.3 Customer Metrics Report (`/customer-metrics-report`)

**Request:**
```json
{
  "sellerworkspaceid": "uuid",
  "limit": 20,
  "offset": 0
}
```

**Response fields (confirmed):**
```
data[].inviteId               uuid       — Customer/invite identifier
data[].customerCode           string     — Customer code or Lead-XXXXX
data[].customerFirmName       string     — Business name
data[].customerName           string     — Contact person name
data[].grossCreditLimit       decimal?   — Credit limit
data[].creditLimitPeriod      string?    — Credit period terms
data[].routes                 string     — Route/territory
data[].segments               string     — Segment tags (e.g. "Retailers, P1 State")
data[].outstandingAmount      decimal?   — Total outstanding
data[].overdueAmount          decimal?   — Overdue amount
data[].latestInvoiceAmount    decimal?   — Most recent invoice value
data[].latestInvoiceDate      date?      — Most recent invoice date
data[].latestInvoiceNumber    string?    — Invoice reference
data[].latestInvoiceId        uuid?      — Invoice ID
data[].latestPaymentAmount    decimal?   — Most recent payment
data[].latestPaymentNumber    string?    — Payment reference
data[].latestPaymentId        uuid?      — Payment ID
data[].latestOrderAmount      decimal?   — Most recent order value
data[].latestOrderDate        date?      — Most recent order date
data[].latestOrderNumber      string?    — Order reference
data[].latestOrderId          uuid?      — Order ID
data[].latestLedgerUpdatedAt  datetime?  — Last ledger update
data[].latestCheckinDate      date?      — Last sales checkin
data[].teamMemberId           uuid?      — Assigned team member ID
data[].teamMemberName         string?    — Assigned team member name
totalRecords                  int        — Total customer count
startRecord                   int        — Pagination start
endRecord                     int        — Pagination end
```

### 2.4 Product View (`/analytics/productview`)

**Request:**
```json
{
  "fromdate": "2026-07-01",
  "enddate": "2026-07-17",
  "offset": 0,
  "limit": 20,
  "metrics": ["current_stock", "inventory_value", "total_revenue"],
  "groupBy": ["item_name"],
  "sortBy": [{"column": "productname", "order": "asc"}]
}
```

**Request-derived schema:**
- `metrics` available: `current_stock`, `inventory_value`, `total_revenue`
- `groupBy` available: `item_name`
- `sortBy` available: `productname`

### 2.5 Payment View (`/analytics/paymentview`)

**Request:**
```json
{
  "fromdate": "2026-07-01",
  "enddate": "2026-07-17",
  "limit": 20,
  "global_filter": {"pos": [], "neg": []},
  "offset": 0,
  "groupBy": ["customername"],
  "ageing": ["0-30", "31-60", ">60", "other"],
  "ageing_on": "due_date",
  "sortBy": [{"column": "customername", "order": "asc"}],
  "include_summary": true
}
```

**Request-derived schema:**
- Ageing buckets: `0-30`, `31-60`, `>60`, `other`
- Ageing basis: `due_date`
- Grouping by: `customername`
- Summary mode available

---

## 3. Field Overlap Analysis

### Common Fields Across All Customer APIs

Only **customerFirmName** and pagination fields (`startRecord`, `endRecord`) are shared. Each API serves a distinct purpose with minimal overlap.

### Unique Value Per API

| API | Unique Data (not available anywhere else) |
|-----|------------------------------------------|
| Customer Metrics Report | Credit limit, credit period, routes, segments, latest invoice/payment/order trail, team assignment, last checkin, customer contact name |
| Sales Analytics | Ranked ordering by totalSales, date-range filtering on invoiceDate |
| Payment View | Ageing buckets (0-30/31-60/>60/other), global filters, summary totals |
| Customer Analytics | Order count vs invoice count comparison metrics (if working) |
| Product View | Stock levels, inventory value, product-level revenue |

### Cross-Entity Links

```
Customer Metrics Report.inviteId          → primary customer identifier
Customer Metrics Report.customerFirmName  → links to Payment View.customername
Customer Metrics Report.customerFirmName  → links to Sales Analytics.customerFirmName
Product View.item_name                    → product-level (no customer link)
```

---

## 4. Chat-Value Assessment

### Dimension Scoring

| Dimension | Description | Sales | CustKPI | CustMetr | Product | Payment |
|-----------|-------------|-------|---------|----------|---------|---------|
| **Entity Identity** | Tells the agent WHO they're talking about | ✗ | ✗ | ✓ | △ | △ |
| **Transaction History** | Shows WHAT has happened recently | △ | △ | ✓ | ✗ | ✓ |
| **Financial Risk** | Indicates RISK (credit, overdue) | ✗ | ✓ | ✓ | ✗ | ✓ |
| **Relationship Context** | Shows TEAM/ROUTE/SEGMENT context | ✗ | ✗ | ✓ | ✗ | ✗ |
| **Actionable Next Step** | Suggests WHAT TO DO NEXT | △ | △ | ✓ | △ | ✓ |
| **Ranking/Priority** | Helps the agent PRIORITIZE | ✓ | ✗ | ✗ | △ | ✓ |

### Feature Matrix

| Feature | Sales | CustKPI | CustMetr | Product | Payment |
|---------|-------|---------|----------|---------|---------|
| Filterable by date range | ✓ | ✓ | ✗ | ✓ | ✓ |
| Custom metrics selection | ✓ | ✓ | ✗ | ✓ | ✗ |
| Group by entity | ✓ | ✗ | ✗ | ✓ | ✓ |
| Sort by any column | ✓ | ✗ | ✗ | ✓ | ✓ |
| Pagination | ✓ | ✗ | ✓ | ✓ | ✓ |
| Credit limit info | ✗ | ✗ | ✓ | ✗ | ✗ |
| Overdue tracking | ✗ | ✓ | ✓ | ✗ | ✓ |
| Ageing buckets | ✗ | ✗ | ✗ | ✗ | ✓ |
| Summary/totals | ✗ | ✗ | ✗ | ✗ | ✓ |
| Stock/inventory | ✗ | ✗ | ✗ | ✓ | ✗ |
| Team member assignment | ✗ | ✗ | ✓ | ✗ | ✗ |
| Segment/route info | ✗ | ✗ | ✓ | ✗ | ✗ |
| Latest transaction trail | ✗ | ✗ | ✓ | ✗ | ✗ |
| Customer name/person | ✗ | ✗ | ✓ | ✗ | ✗ |

---

## 5. Overall Ranking

| Rank | API | Score | Why |
|------|-----|-------|-----|
| **1** | **Customer Metrics Report** | ⭐ **9.5/10** | Full identity + credit + latest transactions + team + segments. Single call = complete context. The only API that answers "who is this customer?" comprehensively. |
| **2** | **Payment View** | **8.5/10** | Overdue tracking by ageing bucket is high-impact for collection follow-up. `include_summary` gives the agent quick totals. No other API provides ageing data. |
| **3** | **Sales Analytics** | **7.5/10** | Ranking is unique value — no other API tells the agent WHO to prioritize. Limited fields but essential for "who should I call today?" queries. |
| **4** | **Customer Analytics** | **6/10** | Financial KPIs overlap with what Customer Metrics Report provides at individual level. Useful only if aggregate across all customers is needed. |
| **5** | **Product View** | **5/10** | Different entity (product vs customer). Valuable for inventory questions but doesn't directly enrich customer conversations. |

### Key Insight

**Customer Metrics Report + Payment View is the highest-value combination.** Together they cover:
- Who the customer is (identity, contact person, firm name)
- Financial risk profile (credit limit, outstanding, overdue)
- Payment discipline (ageing buckets)
- Recent activity (latest invoice, payment, order)
- Relationship context (team member, segments, routes, last checkin)

---

## 6. Recommended Chat Tool Architecture

### Tier 1 — Always-On Context (loaded at conversation start)

```
get_customer_profile(workspace_id, customer_id)
  → Customer Metrics Report (filtered by customer)
  → Returns: firm name, person name, credit limit, outstanding,
    overdue, latest invoice/payment/order, team member, segments
  → Benefit: single call equips the agent with 90% of what it needs
```

### Tier 2 — Query-Specific Tools (called on demand)

```
get_top_customers(workspace_id, from, to, limit)
  → Sales Analytics
  → Answers: "Who are my best customers?" / "Who should I call today?"

get_payment_receivables(workspace_id, from, to)
  → Payment View
  → Answers: "Who's overdue?" / "What do I need to collect?"

get_customer_financials(workspace_id, customer_id, from, to)
  → Customer Analytics
  → Answers: "How many orders vs invoices?" / "What's outstanding?"

get_product_stock(workspace_id, from, to)
  → Product View
  → Answers: "What's low on stock?" / "What's selling best?"
```

### Tier 3 — Combined Power Analysis

**"Why should I visit Customer X today?"**
1. `get_customer_profile(X)` — check credit, team, segments
2. `get_payment_receivables(X)` — check overdue
3. `get_top_customers()` — check their rank

**"What products should I push to Customer X?"**
1. `get_customer_profile(X)` — check their segments/routes
2. `get_product_stock()` — check what's in stock

---

## 7. Open Source Tools for API Schema Comparison

For automating this type of analysis in the future:

| Tool | Purpose | Best For |
|------|---------|----------|
| **OpenAPI Diff / oas-diff** | Compare OpenAPI specs | APIs with formal OpenAPI specs |
| **json-schema-diff** | Compare JSON schemas | When APIs expose schema in JSON Schema |
| **optic** | Capture and diff API behavior | CI-based API change detection |
| **postman-to-openapi** | Convert Postman collections | Normalizing to a common format |
| **jq** + custom scripts | Diff actual JSON payloads | Comparing real responses (no formal spec needed) |
