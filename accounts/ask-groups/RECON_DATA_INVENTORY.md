# Ask Groups Recon — Data Inventory (Zainab Enterprises)

**Run:** 2026-09-23 · `accounts/ask-groups/runs/query_results_v1.jsonl` · 12/12 ok, 0 errors,
avg 14.2s, no clarify, no tool events (backend chat engine — expected; grade behavior/evidence).
**Workspace:** d53279c2-0f92-42ea-876d-1c57770f5184 · login 9029012960 · lane `ask_chats` ·
trace workspace (2026-09-22 exports) — fabric/wallpaper/curtains/furnishings trade.

**VERDICT: workspace VIABLE for AR/collections evals.** Real tagged corpus, live groups,
honest coverage disclosure. Proceed to AR Phase 1.

---

## Data presence (what exists in the groups)

- **Tagged window:** 2026-09-02 → 09-23 (moves as the corpus re-processes; v5 facts table).
- **Coverage — PARTIAL and disclosed:** 6,117/10,041 messages untagged (~61%) in the 7-day
  band; 3 low-volume working days (17/18/19 Sep; normal day ≈ 956 msgs). Every answer carried
  both caveats in the headline. Read ALL counts below through them.
- **Groups:** 570 in parse memory; **257 active** in the last 7 days.
- **Requests (7d, both sides): 1,461** → 872 answered / 401 acknowledged-only / 188 no-response.
- **By kind (7d):** Stock 446 · Dispatch 330 · Order 269 · Other 151 · Price 99 · Invoice 69 ·
  Payment 48 · Catalogue 28 · Ledger 11 · Complaint 10.
- **Response times (customers, 7d):** 900 requests, 67% got a real answer; median first
  reaction **7.8 min**, avg 77.1 min; slowest askers: HARJOT KAUR DECOR STYLISTS (19.8 h,
  9 reqs), Riddhi (18.1 h).
- **Chasing (customers chasing US):** 37 unanswered requests chased ≥1× (Dispatch 14,
  Stock 10, Order 7, …).

## Payment / AR surface (the AR-relevant layer)

- **Payment Follow-up topic (customers, 7d): 9 requests** — 2 answered / 3 acked / 4 no-reply;
  amount mentioned ₹5,192 (1 of 9). **Payment chatter is SPARSE** — AR value on Zainab sits
  mostly in ERP (balances/invoices) with occasional payment-discussion queries.
- **Real AR evidence anchors found in the register (use in AR queries):**
  - "Chq leke gaya tha 2nd sept ko. Not deposited yet??" (Vicky Jain) — cheque lodged 02-Sep,
    not deposited → dispute/evidence case.
  - "NEFT RS.880.00 AGAINST YOUR B NO 15293 DATE 03.09.2026 …" (hiteshvthakkar) —
    invoice-anchored payment mention (invoice ref **B NO 15293**).
  - "PLEASE NEFT OUTSTANDING BALANCE ASAP Al anwar Decor 26-27 c…" (Idris Contractor).
  - "IMPORTANT: Please update bank records. Dear Customer…" (Billing Dept - Pramik Mum).
  - "Can i give me payment bal details. Pls let's close…" (Nisha / Rashida thread).
- Ledger-statement sharing + bank-record-update request types appear in the register (the AR
  ledger-activity leg is present, not just the sales side).

## Customer aliases (as typed in the groups — feed AR identity/CLARIFY, NOT ERP entities)

- **Firm-style:** FINESSE DECOR · GLAMOUR WALLPAPERS · WHISTLING WOOD ENTERPRISES ·
  MOHANLAL COMPANY FURNISHINGS · RIGHT CHOICE.-Shruti · Trends Furnishings · Casa walls ·
  ELEGANT DECORATIVE PRODUCTS · A To Z Furnishing · FAB-RICH OVERSEAS PVT. LTD. ·
  ZEBA INDIA PRIVATE LIMITED · BEAUTY HOME · Purple Patch purchase team ·
  Floor & Furnishings India Pvt Ltd (Upendra Singh) · Eureka · Elementto Fabric Team ·
  Railway-side aliases vary (short names are the norm — ambiguity is real).
- **Person-style:** Ritesh W · Vrushank Satra · Mohsin Saeed · Ashray Mutha · Billa ·
  Asif Mansoori · Dhiraj Jain · Singh Sanjeev · Bhavin Shah · Sunil yadav · Nisha ·
  Rashida Shabbir · Idris Contractor · hiteshvthakkar · Vicky Jain · Ravish Tripathi ·
  Kashish · Sohail shaikh · tausif · SARVESH AGNIHOTRI · HARJOT KAUR DECOR STYLISTS.
- **Group naming:** "<Customer> + Zainab" | "Zainab + <Customer>" | "<X> + ZE" — consistent;
  biggest active groups: RR + Zainab (72 reqs), STOCKING FABRICS (55), Whistling Wood + ZE (41).

## Known gap reproduced

- "How many groups do I have?" → still the intro fallback ("nothing was counted") although
  the 570-group inventory sits in parse memory. Scope gap confirmed live on Zainab
  (trace-1 repro, 2026-09-22). Not an AR blocker; a find for the ask-groups full eval later.

## Implications for AR / collections (feed into Phase 1 of the AR plan)

1. **Proceed.** Workspace viable; AR Phase 1 ERP-side harvest (`query_ar_financials` on
   Zainab: customer balances / invoices / gst) is still REQUIRED — group aliases are the
   conversational side, not the ERP customer master.
2. **Identity-CLARIFY queries:** use firm names AS TYPED here (Finesse Decor, Whistling Wood,
   Casa walls, Right Choice…) — ambiguous against the ERP master is exactly the shortlist
   point.
3. **Payment-chat AR queries should be few and specific** (real rate ≈ 9/7d): anchor on the
   real cases above (B NO 15293, 02-Sep cheque, Al Anwar outstanding) rather than "show all
   payment discussions".
4. **Coverage undercount is inherited:** AR claims/commitments derived from these same
   messages carry the 61%-untagged caveat — hedged/limited AR answers on the WhatsApp leg
   will be CORRECT, not failures.
5. Ask-groups full eval is a separate deliverable (agent never evaled; 3 raw traces exist);
   recon queries are marked RECON and are not a graded baseline.