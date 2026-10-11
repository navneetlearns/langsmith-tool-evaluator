#!/usr/bin/env python3
"""Render an AR-agent eval page (docs/<account>/index.html) — two-tab, plain-language
overview + developer tab. Improves the build_dashboard.py output for the AR accounts.

Reads accounts/<account>/runs/query_results_v<N>.jsonl, computes outcomes with
build_dashboard.classify_quality, and embeds every quote by pulling it from the run file
at build time (no hand-typed transcription). Hand-graded scorecard numbers and narrative
facts are per-account constants in ACCOUNTS below — each cites the query ids it rests on.

Run: python3 scripts/render_ar_dashboard.py [--account NAME] [--run N]
     defaults: --account ar-agent --run 2   (writes langsmith-tool-evaluator/docs/<account>/index.html)

Accounts:
  ar-agent      Zainab Enterprises, 2026-09-24, 56 queries (judged by the user)
  hirafoods-ar  HiraFoods c331ac11, 2026-10-09, 32 queries (judged in-session,
                accounts/hirafoods-ar/runs/judgments_v1.jsonl)
"""
import html as H
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build_dashboard as bd


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


ACCOUNT = arg("--account", "ar-agent")

# ---------------------------------------------------------------- per-account payloads
ACCOUNTS = {
    "ar-agent": {
        "run": 3,
        "fresh_max": 35,
        "title": "Accounts-receivable assistant — 35-question re-run",
        "subtitle": "Answers about who owes what, and what customers said on WhatsApp about paying · Zainab Enterprises · 2026-10-09 · questions 1–35 of the 56-question set",
        "verdict": """Answers that come back are still good — real customers, real commitments, real
  amounts, nothing invented. But <strong>10 of 35 questions got no answer at all</strong>, and every one of
  them sits in the commitment and invoice sections (q11–q23). Five more declined on the claim that the
  WhatsApp chat can’t be read — in the same run, other questions read <strong>116 chat payment claims</strong>
  and quote messages word for word.""",
        "works": [
            "<strong>Counts claims as claims.</strong> <strong>116 unresolved WhatsApp payment claims</strong> (₹70 to ₹5,00,000), named and referenced — reported, not entered, and repeatedly marked “should not yet be treated as received payments”.",
            "<strong>Commitment answers are the run’s best work.</strong> q13 names 4 dated overdue promises (<strong>THE ARTY GARAGE</strong>, SHREE JAIN FOAM &amp; FURNISHINGS-T, MARVEL HOMES) and explains why ONCE &amp; AGAIN can’t be called overdue; q14 finds 25 customers with 42 broken commitments; q17 finds 3 promises with no payment posted.",
            "<strong>Reads the chat when it goes there.</strong> q34 quotes “Credit note send kijiye payment karta hu”; q32 pins a credit-note request to a named person in a named group.",
            "<strong>Clean and honest where it answers.</strong> 0 format violations across 25 answers — no tool names, no run IDs, no made-up figures; q25 says plainly that bill 15293 and the ₹880 NEFT claim were not in the data rather than papering over it.",
        ],
        "scorecard": [
            ("Solid answers", 10, "ok", "✓", "Clear, correct and useful"),
            ("Partial answers", 4, "partial", "◐", "Real data, but the asked comparison was not completed"),
            ("Honest “can’t do”", 5, "ok", "?", "Declined with real numbers and a next step"),
            ("Declined on a false “no chat data” claim", 5, "bad", "✗", "Chat data was readable elsewhere in the same run"),
            ("Wrong answer", 1, "bad", "⚠", "Answered a different question than the one asked"),
            ("No answer at all", 10, "none", "–", "7 fast empty turns + 3 dropped renders (10 of 35)"),
        ],
        "goes": [
            {"title": "Ten questions got silence — all in one stretch of the set", "q": 11,
             "note": "q11, q15 and q22 returned nothing after 28–50 s of tool work (ar_promises, getCustomerAnalytics, ar_worklist) — the tools ran and the answer text never arrived. q12, q16, q18, q19, q20, q21 and q23 bail in 2.2–4.6 s with no tool call and no interrupt event at all. Rows q11–q23 are 13 questions and produced <strong>all 10</strong> of the empty answers, while q1–q10 answered 10/10."},
            {"title": "“The chat data isn’t available” — in a run that reads the chat", "q": 6,
             "note": "q6, q7, q26, q28 and q30 all decline because WhatsApp amounts, UTRs or claims “aren’t available in this session”, and ask you to paste an export. In the same run q2, q4 and q10 returned 116 chat payment claims with names and references, and q25, q32 and q34 quote message content directly. The data is reachable — the routing is what fails."},
            {"title": "One answer answers a different question", "q": 31,
             "note": "“Which payment references are still unresolved?” → “No unresolved payment references were found … 0 payments marked as sent, failed, or cancelled.” That is a status-flag search, not a reference search, and its headline contradicts the 116 unresolved claims q2, q4 and q10 found minutes earlier."},
            {"title": "The designed mismatch case was never answered", "q": 20,
             "note": "“Bill 15293 was claimed as paid on WhatsApp (NEFT ₹880) — is it in ERP?” parked empty. Separately, q25 reports that neither 15293 nor the ₹880 NEFT claim exists in the data and that the ₹880 hit is a price quote — matching v2’s finding that invoice 15293 is not in ERP. The anchor itself needs a decision: wrong query-set anchor, or an unreachable document series."},
        ],
        "good": {
            "q": 13,
            "prefix": "",
            "preamble": "What the user got: four dated overdue commitments with names and dates, plus a correct note that ONCE &amp; AGAIN acknowledged but never gave a date — so no overdue amount can be asserted for it. The strongest answer in the run.",
            "ideal": """<p>“<strong>4 commitments are past their date:</strong> THE ARTY GARAGE (7 Oct, 8 Oct), SHREE JAIN FOAM &amp; FURNISHINGS-T (8 Oct), MARVEL HOMES (8 Oct). ONCE &amp; AGAIN has acknowledged but never dated, so there is nothing to chase on a date. Chase these three today.”</p>""",
            "ideal_note": "Same facts, one line, and the one thing to do next — every figure in it is supported by this run.",
        },
        "dev_failmap": [
            ("No answer: 10 of 35 rows (q11, q12, q15, q16, q18, q19, q20, q21, q22, q23)", [
                "7 fast empty turns: q12, q16, q18, q19, q20, q21, q23 — 2.2–4.6 s, no tool call, status connected→status→status→status→done, ui_payload_type None. No interrupt event fired, so these are NOT clarify parks — nothing was asked and there is nothing to resume. (The interrupt event does reach the wire elsewhere: v2 fired it on 14 rows. What is never persisted is the payload, because run_agent_evals.py does not read res[\"interrupt\"] — a harness gap, not a backend defect. Corrected 2026-10-11.)",
                "3 dropped renders: q11 (45.4 s), q15 (49.7 s), q22 (28.0 s) — tools ran and a ui event was emitted, but no body text arrived. Not parks: too slow, tools called. A second mechanism behind the same symptom.",
                "All 10 sit in q11–q23 (payment commitments + invoices); q1–q10 answered 10/10.",
            ]),
            ("Refusals built on a false availability claim: 5 rows (q6, q7, q26, q28, q30)", [
                "Each declines because WhatsApp amounts, UTR messages or chat claims “aren’t available in this session / current workspace”, and asks for a pasted export.",
                "Same run: ar_payments_reported returned 116 chat claims (q2, q4, q10); search_messages + spawn_filter_agent enumerated invoice numbers from messages (q25); search_threads quoted chat lines (q32, q34).",
                "This is the AR copy of the HiraFoods q9-vs-q24 nondeterminism: one question class, two paths, one silently useless.",
            ]),
            ("Scope slip: q31", [
                "Answered “0 payments marked sent, failed, or cancelled” for a question about unresolved <em>references</em> — a different predicate.",
                "Its headline directly contradicts 116 unresolved claims from three other rows in the same run.",
            ]),
            ("Tool surface: three runs, three surfaces", [
                "v2 (2026-09-24) ran query_ar / get_ar_evidence / get_ar_schema / query_ar_financials / resolve_ar_customer; this run ran get_collections, ar_payments_reported, ar_promises, getCustomerAccountData, search_threads — and no query_ar* at all.",
                "New to every prior inventory: spawn_filter_agent (q25, q34 — the lane spawns a sub-agent), getCustomerAccountData, getCustomerAnalytics.",
                "resolve_ar_customer never fired, so v1’s exact-match resolver defect is untested here rather than fixed; the one customer-anchored lookup (q5) went through search_customers_master and worked.",
            ]),
        ],
        "dev_bugs": [
            ("q31", "answers a status-flag question instead of “unresolved reference”; contradicts q2/q4/q10"),
            ("q11, q15, q22", "tools complete + ui event, empty body — dropped render, not a clarify park"),
            ("q12, q16, q18–q21, q23", "empty in ≤5 s with NO interrupt event — not a clarify park; unexplained empty turn"),
            ("q6, q7, q26, q28, q30", "refuse on “WhatsApp data unavailable” while the same run reads chat claims and quotes messages"),
            ("q20", "designed WhatsApp-vs-ERP mismatch anchor parked; q25 reports 15293 / ₹880 absent from the data"),
            ("q5", "the only customer-anchored lookup used search_customers_master and succeeded — different path from v2"),
            ("q1, q3, q5, q27", "cross-match stopped at a preview/truncation limit instead of paging (5 of 15 receipts shown)"),
        ],
        "dev_numbers": [
            ("Unresolved WhatsApp claims", "q2, q4, q10", "116 claims · ₹70 – ₹5,00,000"),
            ("ERP payments", "q6, q7, q26, q28, q30", "3,069 receipts · ₹21.08Cr · 9 Oct 2025 – 9 Oct 2026"),
            ("ERP bills vs receipts", "q24", "16,616 bills · 3,069 receipts"),
            ("Broken commitments", "q14", "25 customers · 42 commitments · 15 Sep → 8 Oct"),
            ("Total receivables", "q35", "₹16,90,46,880.32"),
            ("Ledger entries sampled", "q33", "first 20 of 3,048"),
        ],
        "dev_numbers_note": "<span class=\"flag\">Worth a human check:</span> q35’s ₹16,90,46,880.32 “across the customer base” is a different scope from v1’s Zainab position of ₹233.22 Cr outstanding (entities.json, as of 2026-09-21) — two tools, two scopes, ~14× apart. Confirm which is authoritative before quoting either. Unlike v2, this run shows no exact-100× scaling pair.",
        "dev_harness": [
            "Scope: questions 1–35 of the 56-row set were live-run on 2026-10-09; rows q36–q56 are carry-over from v2, byte-identical, NOT re-run. Sections 6–8 and both CLARIFY controls (q46, q51) were not exercised.",
            "Analyzer figures here are fresh-35 scope: strict tool accuracy 13/35 (37%), lenient 27/35 (77%), 0 format violations. The unfiltered --run 3 call also counts the 21 carried rows.",
            "Scorecard is hand-graded per row; raw classifier buckets for the fresh 35: success 22, marginal 2, no_data 1, clarify-park 7, fail 3.",
            "Hedge metric: the Hinglish HEDGE_RE scores 4/25 while most refusals hedge in English (“can’t reliably”, “without guessing”) — the same regex-gap class seen earlier, now inverted.",
            "The set still has no REFUSE rows, so refusal-correctness remains untested on this account (v1 gap, unchanged).",
        ],
        "dev_fix": [
            "Persist res[\"interrupt\"] in run_agent_evals.py (1 line) — the payload is captured by the parser and then dropped by the runner, so clarify questions are lost even when sent. Harness-side; do this before filing anything against the backend.",
            "Investigate the 10 interrupt-free empty turns — 7 bailed in 2–5 s with no tool call, 3 (q11, q15, q22) ran tools then dropped the render. A different mechanism from the v2 parks; fixing the runner does not close these.",
            "Route to the wired chat tools before declining (5 rows) — the availability claim is false on this workspace.",
            "Answer the asked predicate (q31), and pin the tool surface per run before any strict-% is read as agent skill.",
            "Decide the q20 anchor: correct the query set or fix the lookup, then say which.",
        ],
        "latency_note": "Overall mean 26.9 s, median 23.6 s (35 queries; min 2.2 s, max 81.6 s — q34, message search + spawn_filter_agent). Silent parks bail at 3.8 s average. No SSE errors, no 402 quota trips. Better tail than v2 (mean 23.4 s, max 232.7 s).",
        "footer_score": "Scoring is hand-graded by a reviewer against this run file (solid 10 · partial 4 · honest “can’t do” 5 · false-unavailable refusal 5 · wrong 1 · no answer 10). Row-level reasoning: accounts/ar-agent/EVAL_READOUT_v2.md.",
    },

    "hirafoods-ar": {
        "run": 2,
        "title": "Accounts-receivable assistant — 32-question HiraFoods test",
        "subtitle": "Answers about who owes what, and what customers said on WhatsApp about paying · HiraFoods (AU Bank workspace) · 2026-10-09",
        "verdict": """It works when the question is about the whole workspace or about what customers said on
  WhatsApp — real totals, real claims, real promises, and it never pretended a claim was a payment.
  It breaks the moment the question starts from a customer name or an invoice number: those two
  lookups return “not found” even for records that plainly exist. 19 of 32 rows are usable; the 13
  that aren’t split into 6 on those two lookups, 3 scope errors, 2 silent empty answers and 2
  one-off failures.""",
        "works": [
            "<strong>Real numbers, correctly scoped.</strong> Total outstanding <strong>₹57,77,21,622.19</strong>, <strong>14,592+</strong> pending invoices, collections <strong>₹36,255.75</strong> for 01–09 Oct — all read from the receivables/collections tools, not invented.",
            "<strong>Never lets a claim look like a payment.</strong> A customer’s “All settled from our side” is reported as a claim and explicitly flagged <em>“received ya entered confirm nahi maana ja sakta”</em>.",
            "<strong>Refuses properly, twice.</strong> “Supply band kar du?” and “outstanding pichle hafte se badha?” both got honest refusals with a safe alternative offer — no fabricated trend, no action taken.",
            "<strong>Zero format violations, zero fabrication.</strong> No tool names, no run IDs, no made-up customers or amounts anywhere in the 32 answers; 18 of 30 non-empty answers hedge the confirmability of what they report.",
        ],
        "scorecard": [
            ("Solid answers", 7, "ok", "✓", "Clear, correct and useful"),
            ("Good but hedged", 6, "partial", "◐", "Honest, but narrower than asked"),
            ("Asked a follow-up", 3, "ok", "?", "Correctly asked instead of guessing"),
            ("Refused correctly", 3, "ok", "–", "Said plainly it can’t / shouldn’t"),
            ("Wrong or unusable", 11, "bad", "✗", "Lookups that failed, over-refusals, out-of-scope answers"),
            ("No answer at all", 2, "none", "–", "Empty responses (2 of 32)"),
        ],
        "goes": [
            {"title": "The customer name your business uses isn’t found", "q": 1,
             "note": "“Lakshmi Agencies” and “Laxmi Agency” both come back “koi match nahi mila” — while the WhatsApp side resolves the same customer as <strong>Lakshmi Agencies &amp; Co 84</strong> and can quote their invoices and amounts (q6, q7, q23). The name a person types and the name the system answers to are not the same, and only one of them works."},
            {"title": "Invoice numbers the chats talk about aren’t found in the books", "q": 12,
             "note": "INV-4007, INV-4009 and INV-4013 all return “invoice record nahi mila” — yet INV-4007’s payment claim and INV-4009’s invoice number are sitting in the messages (q3, q17), and <strong>14,592</strong> pending invoices are available (q15). Invoice questions route to the invoice list; chat mentions come from a different store."},
            {"title": "Two questions got silence", "q": 13,
             "note": "“invoice 4008 ka kya hua?” and the follow-up “aur INV-4011?” returned an <strong>empty answer</strong> after 27 s and 12 s — no data, no question back, and no event the harness could even flag. Nothing on the page tells the user why."},
            {"title": "Questions outside receivables get answered anyway", "q": 29,
             "note": "“Ultra Biscuits Regular ka stock kitna bacha?” and “Diamond Juice Strong ka rate kya hai?” were <strong>answered</strong> with real product data (stock, rate) instead of being declined. The receivables assistant has product tools wired in, so it steps outside its own scope."},
        ],
        "good": {
            "q": 1,
            "prefix": "",
            "preamble": "What the user got: an honest “not found” and a request for a mobile number — on a customer the system already knows. Nothing was invented, but nothing was answered either.",
            "ideal": """<p>“<strong>Lakshmi Agencies &amp; Co 84</strong> — 12 overdue bills, overdue balance <strong>₹1,78,611.84</strong>. Unhone INV-4007 ke liye “All settled from our side” bola tha — woh claim abhi ledger mein confirm nahi hua, aur INV-4011 ke liye ₹5,48,000 ka acknowledgement darj hai.”</p>""",
            "ideal_note": "Both sides of the story on one line — ledger position, the customer’s claim, and the acknowledgement — instead of an identity dead-end. Every figure is real: the overdue position comes from the read-only gate probe (runs/gate_probe_v1.jsonl), the acknowledgement from this run.",
        },
        "dev_failmap": [
            ("Customer-name resolution: 5 rows affected, 3 lost (q1, q2, q4, q5, q32; + q27 deflected)", [
                "Every name-anchored row that needs a resolve died: search_customers_master returned no match for “Lakshmi Agencies” / “Laxmi Agency”.",
                "The signal side resolves the same party: ar_promises (q6, q23) and ar_payments_reported (q7) name “Lakshmi Agencies & Co 84” with invoice refs and amounts.",
                "q8 shows the same split on groups: candidates were “Lakshmi Agencies & Co 27 / Lakshmi Suppliers & Co 90 / Lakshmi Distributors & Co 70” — the real group “Laxmi Agency + Hirafoods” was not among them.",
                "q27 asked a textbook clarify for the same name in the run, but the pre-run probe answered ORDER status instead — behaviour is not stable across runs.",
            ]),
            ("Invoice-number lookup: 6 rows affected, 5 lost (q11, q12, q13, q14, q19, q20)", [
                "list_invoices / getCustomerAccountData: “INV-4007 record nahi mila”, “INV-4009 account record nahi mila”, “INV-4013 nahi mila”.",
                "Meanwhile get_receivables reports 14,592 pending invoices and search_messages quotes INV-4688, INV-4014 and INV-4009 from the chats (q17).",
                "q13 returned nothing at all; q19 refused the whole paid/unpaid question instead of reading receivables.",
            ]),
            ("Silent empty responses: 2 rows (q13, q28)", [
                "Empty body, no tool call, no error, no `interrupt` event — parks=[] in the analyzer, which is why the runner cannot flag or resume them.",
                "Same class as AR v1's 12 empty parks and finance P1: the question never reaches the wire.",
            ]),
            ("Out-of-scope answers: 2 rows (q29, q31)", [
                "search_product_master was called twice inside the receivables lane and produced stock/rate answers.",
                "list_dispatch_notes / list_orders are likewise reachable (q16, q27-probe) — the lane is not tool-scoped to receivables.",
            ]),
            ("Tool choice is not deterministic for one question class (q9 vs q24)", [
                "q9 “sabse zyada kis party ka payment baaki hai?” → getCustomerAccountData → “data fetch nahi kar paaya”.",
                "q24 “top 5 party by outstanding” → get_receivables → answered, highest balance ₹20.48L.",
                "Same intent, two paths, one silently fails.",
            ]),
        ],
        "dev_bugs": [
            ("q1, q2, q4, q5, q32", "name-anchored turns collapse — the WhatsApp display name does not resolve against the customer master"),
            ("q12, q14, q20", "invoice lookup returns “not found” for invoices the message store quotes"),
            ("q13, q28", "empty response, no interrupt event, no tool call (26.8 s / 11.9 s, 7 status events) — unexplained empty turn, not a clarify park"),
            ("q29, q31", "out-of-scope product stock/rate answered instead of refused"),
            ("q9", "same question class as q24 failed to fetch via getCustomerAccountData"),
            ("q19", "over-refused a supported capability (unpaid status) while q15/q21/q25 read the same data"),
            ("q6, q17, q24", "register drift: Devanagari (q14), English (q24), Hinglish (most) inside one run"),
        ],
        "dev_numbers": [
            ("Workspace total outstanding", "q21 vs gate probe", "₹57,77,21,622.19 — identical in both"),
            ("Pending invoices", "q15 vs gate probe", "14,592+ — identical"),
            ("Lakshmi overdue", "gate probe", "12 overdue bills · ₹1,78,611.84"),
            ("Lakshmi acknowledgement", "q6", "INV-4011 ₹5,48,000 (new evidence, not in the draft anchors)"),
            ("Lakshmi commitments", "q23", "by 10-Oct · ₹1,460.88 by 20-Oct — matches the draft anchors"),
            ("Top customer balance", "q24", "₹20.48L (verify on the AR dashboard — wide spread vs the ₹57.77Cr total)"),
        ],
        "dev_numbers_note": "<span class=\"flag\">Worth a human check:</span> q24's highest party (₹20.48L) against a ₹57.77Cr workspace total is a wide spread — confirm ₹20.48L is a genuine top balance and not a truncated page. No scaling inconsistency was found (unlike Zainab v1's exact-100× pair).",
        "dev_harness": [
            "expected_tool labels came from the 6-probe gate surface; the full run deployed 13 tools, so strict accuracy is 9/27 (28%), lenient 21/27 (66%) — a label artifact, not agent error (v1 action 4, again).",
            "Not one query_ar-family tool fired on this workspace — the D6 assumption from the run plan is wrong here; the surface is the ERP 5-tool contract + ar_promises/ar_payments_reported + product/dispatch tools.",
            "parks=[] is misleading: q13/q28 are empty WITHOUT an interrupt event, so the analyzer cannot see them. Count empty-response rows separately.",
            "The hedge metric needed a Hinglish-aware regex — the English-only pattern scored 2/30 hedged against answers that hedge in every other line.",
        ],
        "dev_fix": [
            "Resolver alias matching (or resolve from the signal side's customer identity) — 5 rows, the single biggest win.",
            "Invoice-number namespace: say which series was searched, and make the chat-quoted series findable — 6 rows.",
            "q13/q28 empty turns: no interrupt event fired, so nothing was asked — diagnose why the turn ended empty (and persist res[\"interrupt\"] in the runner so a real clarify is ever visible).",
            "Tool-scope the lane so receivables refusal actually holds for stock/rate/dispatch questions — 2 rows.",
            "Then re-map expected_tool labels to the observed 13-tool surface before v3.",
        ],
        "latency_note": "Overall mean 16.3 s, median 15.2 s (32 queries; min 1.8 s, max 60.6 s — q3, the message-search + filter-agent chain). Compared with AR v1 on Zainab (mean 23.4 s, max 232.7 s) this workspace is materially faster.",
        "footer_score": "Scoring is hand-graded by a human reviewer against this run file (solid 7 · hedged 6 · clarify 3 · refused 3 · wrong or unusable 11 · no answer 2; per-row verdicts in runs/judgments_v1.jsonl).",
    },
}

cfg = ACCOUNTS[ACCOUNT]
RUNS = ROOT / "accounts" / ACCOUNT / "runs"
OUT = ROOT / "langsmith-tool-evaluator/docs" / ACCOUNT / "index.html"
RUN = int(arg("--run", cfg["run"]))
recs = [json.loads(l) for l in (RUNS / f"query_results_v{RUN}.jsonl").read_text().splitlines()]
# carry-over rows: --only runs pre-seed untouched rows from the previous version so the file
# stays diffable. The page shows only what THIS run actually executed.
if cfg.get("fresh_max"):
    recs = [r for r in recs if r.get("query_index", 0) <= cfg["fresh_max"]]
by = {r["query_index"]: r for r in recs}
N = len(recs)


# ---------------- markdown-lite -> HTML (strip escapes, real tables) ----------------
def clean(s):
    s = re.sub(r"\\([^\da-zA-Z])", r"\1", s)   # \* \. \( \) \\, etc.
    return H.unescape(s)                        # &amp; -> &, &quot; -> "


def inline(t):
    t = clean(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"\*+", "", t)   # no legit asterisks in these answers; drop strays
    return t


def md_to_html(s):
    if not s:
        return "<p class=empty>No answer.</p>"
    lines = s.split("\n")
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("### "):
            out.append(f"<h4>{inline(ln[4:])}</h4>")
        elif ln.startswith("> "):
            out.append(f"<p class=quote>{inline(ln[2:])}</p>")
        elif ln.strip().startswith("- "):
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append(f"<li>{inline(lines[i].strip()[2:])}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif ln.startswith("|"):
            rows, i2 = [], i
            while i2 < len(lines) and lines[i2].startswith("|"):
                rows.append(lines[i2])
                i2 += 1
            rows = [r for r in rows if not re.match(r"^\|[\s:|-]+\|$", r)]
            if rows:
                tbl = ["<table>"]
                for ri, row in enumerate(rows):
                    cells = [c.strip() for c in row.strip().strip("|").split("|")]
                    tag = "th" if ri == 0 else "td"
                    tbl.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
                tbl.append("</table>")
                out.append("".join(tbl))
                i = i2
                continue
        elif ln.strip():
            out.append(f"<p>{inline(ln.strip())}</p>")
        i += 1
    return "\n".join(out)


def snippet(qi, limit=480):
    s = clean(by[qi].get("response") or "")
    if len(s) > limit:
        cut = s.rfind(".", 0, limit)
        s = s[: cut if cut > 200 else limit] + " …"
    return md_to_html(s)


# ---------------- outcomes ----------------
OUT_LABEL = {"success": "Answered", "marginal": "Partial", "no_data": "No data",
             "clarify": "No answer", "fail": "No answer"}


def outcome(r):
    return bd.classify_quality(r)


cats = []
for r in recs:
    if r.get("category") not in cats and r.get("category"):
        cats.append(r["category"])
cat_orders = sorted(cats)
by_outcome = Counter(outcome(r) for r in recs)

lat = defaultdict(list)
for r in recs:
    lat[outcome(r)].append(r.get("response_time_seconds") or 0)


def lats(k):
    v = sorted(lat[k])
    return len(v), (round(sum(v) / len(v), 1) if v else 0), (round(median(v), 1) if v else 0)


all_t = sorted(r.get("response_time_seconds") or 0 for r in recs)

# ---------------- explorer data ----------------
expl = []
for r in recs:
    expl.append({
        "i": r["query_index"], "cat": r.get("category") or "—",
        "out": OUT_LABEL[outcome(r)],
        "q": clean(r.get("query") or ""),
        "a": None,  # filled below after md render (keep clean text + render client-free)
        "s": round(r.get("response_time_seconds") or 0),
    })
for e in expl:
    t = re.sub(r"<[^>]+>", " ", md_to_html(clean(by[e["i"]].get("response") or "")))
    t = re.sub(r"\s+", " ", t).strip()
    e["a"] = (t[:420] + " …") if len(t) > 420 else t

# ---------------- raw input/output: FULL, untrimmed, per query ----------------
# Every row of the run file verbatim: thread_id, the exact input string, the whole
# response body (no 420/480-char trim), raw tool_calls JSON, status sequence, timing.
# The explorer table above stays trimmed for scanning; this is the audit surface.
Q = lambda s: H.escape("" if s is None else str(s))
raw_idx, raw_blocks_html = [], []


def pre(s):
    return '<pre class="io">' + Q(s) + "</pre>"


for r in recs:
    qi = r["query_index"]
    o = OUT_LABEL[outcome(r)]
    chip = f"chip-{o.lower().replace(' ', '-')}"
    tid = r.get("thread_id") or "(none recorded)"
    resp = clean(r.get("response") or "")
    tools = r.get("tool_calls") or []
    if resp.strip():
        out_html = md_to_html(resp)
    else:
        out_html = ('<p class="empty">(EMPTY response — no body, no error field, '
                    'no interrupt event: an unexplained empty turn, not a clarify park)</p>')
    tools_html = pre(json.dumps(tools, indent=2, ensure_ascii=False)) \
        if tools else '<p class="empty">(no tool calls recorded)</p>'
    seq = r.get("status_sequence") or []
    meta = "".join(
        f"<tr><th>{Q(k)}</th><td>{Q(v if v is not None else '—')}</td></tr>"
        for k, v in [
            ("category", r.get("category") or "—"),
            ("expected_tool", r.get("expected_tool") or "—"),
            ("expected_behavior", r.get("expected_behavior") or "—"),
            ("response_time_seconds", r.get("response_time_seconds")),
            ("ui_payload_type", r.get("ui_payload_type")),
            ("error", r.get("error")),
            ("suggestions", json.dumps(r.get("suggestions") or [], ensure_ascii=False)),
        ])
    raw_idx.append(
        f'<tr data-out="{Q(o)}"><td class="qi">q{qi}</td>'
        f'<td><a class="tidlink" href="#raw-q{qi}">{Q(tid)}</a></td>'
        f'<td><span class="chip {chip}">{Q(o)}</span></td>'
        f'<td class="s">{round(r.get("response_time_seconds") or 0)}s</td>'
        f'<td class="qcol">{Q(clean(r.get("query") or "")[:110])}</td></tr>')
    raw_blocks_html.append(f"""<details class="raw" id="raw-q{qi}">
<summary><span class="qi">q{qi}</span> <span class="rq">{Q(clean(r.get('query') or ''))}</span>
 <span class="chip {chip}">{Q(o)}</span> <code class="tid">{Q(tid)}</code></summary>
<div class="rawgrid">
  <div class="rawcell"><h4>Thread ID</h4><div class="tidfull"><code>{Q(tid)}</code></div>
    <p class="note">One thread per query — resume/replay this thread against
    <code>/hub/copilot/threads</code> with the workspace in accounts/{ACCOUNT}/config.yaml.</p></div>
  <div class="rawcell"><h4>Record metadata</h4><table class="numt">{meta}</table></div>
  <div class="rawcell wide"><h4>Input — raw query, exactly as sent</h4>{pre(r.get('query') or '')}</div>
  <div class="rawcell wide"><h4>Output — full raw response, untrimmed</h4><div class="ans">{out_html}</div></div>
  <div class="rawcell wide"><h4>Tool calls — raw JSON</h4>{tools_html}</div>
  <div class="rawcell wide"><h4>Status sequence ({len(seq)} events)</h4>{pre(' -> '.join(seq) or '(none)')}</div>
</div>
</details>""")

raw_idx_html = "".join(raw_idx)
raw_html = "".join(raw_blocks_html)

# ---------------- page ----------------
def table_region(qi, heading, max_rows=8):
    """Render the table that follows '### <heading>' in the response, as real HTML."""
    s = clean(by[qi].get("response") or "")
    lines = s.split("\n")
    start = None
    for i, ln in enumerate(lines):
        if re.search(r"#{1,4}\s*📊?\s*" + heading, ln):
            start = i
            break
    rows = []
    if start is not None:
        for ln in lines[start + 1:]:
            if ln.startswith("|"):
                rows.append(ln)
            elif rows:
                break
    if not rows:
        return snippet(qi, 300)
    rows = [r for r in rows if not re.match(r"^\|[\s:|-]+\|$", r)]
    tbl = ["<table>"]
    for ri, row in enumerate(rows[:max_rows]):
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        tag = "th" if ri == 0 else "td"
        tbl.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
    tbl.append("</table>")
    return "".join(tbl)


def card_goes(g):
    q = Q(clean(by[g["q"]]["query"]))
    body = g.get("table") and table_region(g["q"], g["table"]) or snippet(g["q"], 420)
    return f"""<div class="card">
  <h3>{g['title']}</h3>
  <p class="qq"><span class="qmark">Q</span> “{q}” <span class="qi">q{g['q']}</span></p>
  <div class="ans">{body}</div>
  <p class="note">{g['note']}</p>
</div>"""


exp_rows = "".join(
    f'<tr data-cat="{Q(e["cat"])}" data-out="{Q(e["out"])}"><td class="qi">q{e["i"]}</td>'
    f'<td class="qcol">{Q(e["q"][:110])}</td><td><span class="chip chip-{e["out"].lower().replace(" ","-")}">{e["out"]}</span></td>'
    f'<td class="s">{e["s"]}s</td><td class="acol">{Q(e["a"])}</td></tr>'
    for e in expl)

HTML_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{ --bg:#f8fafc; --card:#ffffff; --ink:#0f172a; --mut:#475569; --line:#e2e8f0;
 --acc:#2563eb; --ok:#15803d; --bad:#b91c1c; --warn:#b45309; --none:#64748b; --soft:#f1f5f9; }
@media (prefers-color-scheme: dark){ :root{ --bg:#0b1220; --card:#111a2e; --ink:#e2e8f0;
 --mut:#94a3b8; --line:#1e293b; --acc:#60a5fa; --ok:#4ade80; --bad:#f87171; --warn:#fbbf24;
 --none:#94a3b8; --soft:#172033; } }
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);
 font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:28px 18px 60px}
header h1{font-size:24px;margin:0 0 4px} header p{color:var(--mut);margin:2px 0}
.tabs{display:flex;gap:8px;margin:22px 0 4px;border-bottom:2px solid var(--line)}
.tabs button{background:none;border:none;padding:10px 16px;font-size:15px;cursor:pointer;
 color:var(--mut);border-bottom:3px solid transparent;margin-bottom:-2px}
.tabs button.on{color:var(--acc);border-color:var(--acc);font-weight:600}
.pane{display:none} .pane.on{display:block;animation:fade .18s ease}
@keyframes fade{from{opacity:0}to{opacity:1}}
.verdict{font-size:17px;background:var(--card);border:1px solid var(--line);
 border-left:4px solid var(--acc);border-radius:10px;padding:16px 18px;margin:16px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:14px 0}
.tile{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 12px;text-align:center}
.tile-icon{font-size:20px} .tile-n{font-size:30px;font-weight:700;margin:2px 0}
.tile-l{font-size:12px;color:var(--mut);line-height:1.3}
.tile-ok .tile-icon{color:var(--ok)} .tile-bad .tile-icon{color:var(--bad)}
.tile-partial .tile-icon{color:var(--warn)} .tile-none .tile-icon{color:var(--none)}
h2{font-size:20px;margin:34px 0 10px} h3{font-size:16px;margin:0 0 8px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:12px 0}
.qq{color:var(--mut);font-style:italic;margin:2px 0 10px} .qi{font-style:normal;font-size:12px;color:var(--mut)}
.qmark{display:inline-block;background:var(--soft);border-radius:6px;padding:0 7px;font-weight:700;color:var(--acc)}
.ans{background:var(--soft);border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-size:13.5px;overflow-x:auto}
.ans table{border-collapse:collapse;margin:6px 0;font-size:13px}
.ans th,.ans td{border:1px solid var(--line);padding:4px 9px;text-align:left}
.ans th{background:var(--card)} .note{color:var(--mut);font-size:13.5px;margin:10px 0 0}
ul{margin:6px 0;padding-left:22px} .quote{color:var(--mut)}
.compare{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media (max-width:760px){.compare{grid-template-columns:1fr} .grid{grid-template-columns:repeat(2,1fr)}}
.filters{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0;align-items:center}
.filters select{background:var(--card);color:var(--ink);border:1px solid var(--line);
 border-radius:8px;padding:7px 10px;font-size:14px}
.tblwrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:12px}
table.tbl{border-collapse:collapse;width:100%;font-size:13.5px;min-width:720px}
.tbl th{text-align:left;background:var(--soft);padding:9px 12px;border-bottom:1px solid var(--line)}
.tbl td{padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}
.qcol{font-weight:600;max-width:270px} .acol{color:var(--mut);max-width:380px}
.s{white-space:nowrap;color:var(--mut)}
.chip{display:inline-block;border-radius:99px;padding:2px 10px;font-size:12px;border:1px solid}
.chip-answered{color:var(--ok);border-color:var(--ok)}
.chip-partial{color:var(--warn);border-color:var(--warn)}
.chip-no-data{color:var(--none);border-color:var(--none)}
.chip-asked-a-follow-up{color:var(--acc);border-color:var(--acc)}
.chip-no-answer{color:var(--bad);border-color:var(--bad)}
.rowcount{color:var(--mut);font-size:13px}
.fn{color:var(--mut);font-size:12.5px;border-top:1px solid var(--line);margin-top:34px;padding-top:12px}
ol{margin:6px 0;padding-left:24px} ol li{margin:4px 0}
.fm{margin:10px 0} .fm h3{margin-bottom:4px} .fm p{margin:3px 0;color:var(--mut);font-size:14px}
code{background:var(--soft);border:1px solid var(--line);border-radius:5px;padding:0 5px;font-size:12.5px}
table.numt{border-collapse:collapse;width:100%;margin:8px 0 4px;font-size:14px}
.numt th,.numt td{border:1px solid var(--line);padding:7px 11px;text-align:left}
.numt th{background:var(--soft)} .flag{color:var(--bad);font-weight:600}
.raw{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px;margin:10px 0}
.raw summary{cursor:pointer;font-size:14px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.raw summary .rq{font-weight:600}
.raw summary .qi{min-width:26px}
.tid{font-size:11.5px;color:var(--mut)}
.tidlink{color:var(--acc);font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;text-decoration:none;word-break:break-all}
.tidlink:hover{text-decoration:underline}
.tidfull code{display:block;padding:7px 9px;word-break:break-all;font-size:12.5px}
.rawgrid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}
.rawcell{background:var(--soft);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.rawcell.wide{grid-column:1/-1}
.rawcell h4{margin:0 0 6px;font-size:13px;color:var(--mut);text-transform:uppercase;letter-spacing:.03em}
pre.io{margin:0;white-space:pre-wrap;word-break:break-word;font-size:12.5px;background:var(--card);
 border:1px solid var(--line);border-radius:8px;padding:9px 11px;max-height:360px;overflow:auto}
@media (max-width:760px){.rawgrid{grid-template-columns:1fr}}
</style></head><body><div class="wrap">

<header>
  <h1>__H1__</h1>
  <p>__SUB__</p>
</header>

<div class="tabs">
  <button class="on" data-tab="ov">Overview</button>
  <button data-tab="dev">For developers</button>
  <button data-tab="raw">Raw I/O &amp; thread IDs</button>
</div>

<section class="pane on" id="pane-ov">
  <div class="verdict">__VERDICT__</div>

  <h2>Scorecard</h2>
  <div class="grid">__SCORECARD__</div>

  <h2>What works</h2>
  <div class="card">
    <ul>
__WORKS__
    </ul>
  </div>

  <h2>What goes wrong</h2>
  __GORES__

  <h2>What a good answer looks like</h2>
  <div class="compare">
    <div class="card"><h3>What the assistant gave</h3>
      <p class="qq"><span class="qmark">Q</span> “__GOODQ__” <span class="qi">q__GOODQI__</span></p>
      <div class="ans">__GOODACT__</div>
      <p class="note">__GOODNOTE__</p>
    </div>
    <div class="card"><h3>Ideal answer</h3>
      <div class="ans" style="background:transparent;border:2px solid var(--ok)">
        __IDEAL__
      </div>
      <p class="note">__IDEALNOTE__</p>
    </div>
  </div>

  <h2>All __N__ questions</h2>
  <div class="filters">
    <select id="f-cat"><option value="">All categories</option>__OPTS__</select>
    <select id="f-out"><option value="">All outcomes</option><option>Answered</option><option>Partial</option><option>No data</option><option>No answer</option></select>
    <span class="rowcount" id="rc">Showing all __N__ questions</span>
  </div>
  <div class="tblwrap"><table class="tbl">
    <thead><tr><th>#</th><th>Question</th><th>Outcome</th><th>Time</th><th>Answer (trimmed)</th></tr></thead>
    <tbody id="tbody">__ROWS__</tbody>
  </table></div>
</section>

<section class="pane" id="pane-dev">
  <h2>Failure map, ordered by impact</h2>
  __FAILMAP__
  <h2>Bug list</h2>
  <table class="numt"><thead><tr><th>Queries</th><th>Issue</th></tr></thead><tbody>__BUGS__</tbody></table>
  <h2>Number consistency</h2>
  <table class="numt"><thead><tr><th>Entity / metric</th><th>View / source</th><th>Value</th></tr></thead><tbody>__NUMS__</tbody></table>
  <p class="note">__NUMSNOTE__</p>
  <h2>Harness notes</h2>
  <ul>__HARNESS__</ul>
  <h2>Latency</h2>
  <table class="tbl" style="min-width:0"><thead><tr><th>Outcome</th><th>Count</th><th>Mean (s)</th><th>Median (s)</th></tr></thead><tbody>__LAT__</tbody></table>
  <p class="note">__LATNOTE__</p>
  <h2>Suggested fix order</h2>
  <ol>__FIX__</ol>
  <p class="fn">Hand-graded, no ground-truth baseline exists. Judgment is a human reviewer’s, not the file’s; machine counts in the developer tab are computed from the run file.</p>
</section>

<section class="pane" id="pane-raw">
  <h2>Thread IDs — one per query</h2>
  <p class="note">Every record in the run file carries its own <code>thread_id</code>: the conversation
  thread the harness created for that query. Click a thread ID to jump to its full raw
  input/output below; resume or replay it against <code>/hub/copilot/threads</code> with the
  workspace in the account’s <code>config.yaml</code>.</p>
  <div class="tblwrap"><table class="tbl">
    <thead><tr><th>#</th><th>Thread ID</th><th>Outcome</th><th>Time</th><th>Question</th></tr></thead>
    <tbody>__RAWIDX__</tbody>
  </table></div>

  <h2>Full raw input/output</h2>
  <p class="note">Audit surface: the exact input string sent, the whole response body with no
  trimming, the raw <code>tool_calls</code> JSON, the SSE status sequence, and record metadata —
  every row of <code>__FILE__</code> verbatim.</p>
  __RAW__
</section>

<p class="fn">__FOOTER__ Accounts __ACCOUNT__, run v__RUN__, file __FILE__ (__N__ records). Scoring is hand-graded by a human reviewer; there is no ground-truth baseline for these answers — treat the numbers as judgment, and the quoted answers on this page as taken verbatim from the run.</p>
</div>
<script>
var tabs=document.querySelectorAll('.tabs button');tabs.forEach(function(b){b.onclick=function(){
 tabs.forEach(function(x){x.classList.remove('on')});b.classList.add('on');
 document.querySelectorAll('.pane').forEach(function(p){p.classList.remove('on')});
 document.getElementById('pane-'+b.dataset.tab).classList.add('on');window.scrollTo(0,0);}});
function rep(){var c=document.getElementById('f-cat').value,o=document.getElementById('f-out').value,n=0;
 document.querySelectorAll('#tbody tr').forEach(function(tr){
  var ok=(!c||tr.dataset.cat===c)&&(!o||tr.dataset.out===o);tr.style.display=ok?'':'none';if(ok)n++;});
 document.getElementById('rc').textContent='Showing '+n+' of __N__ questions';}
document.getElementById('f-cat').onchange=rep;document.getElementById('f-out').onchange=rep;
</script>
</body></html>"""

# ---- assemble ----
score = "".join(f'<div class="tile tile-{c}" title="{_d}"><div class="tile-icon">{ic}</div><div class="tile-n">{n}</div><div class="tile-l">{lab}</div></div>'
                for lab, n, c, ic, _d in cfg["scorecard"])

gores = "\n".join(card_goes(g) for g in cfg["goes"])

goodq = clean(by[cfg["good"]["q"]]["query"])
good_block = cfg["good"].get("prefix", "") + snippet(cfg["good"]["q"], 500)

opts = "".join(f'<option>{Q(c)}</option>' for c in cat_orders)

fm = ""
for title, items in cfg["dev_failmap"]:
    fm += f'<div class="fm"><h3>{title}</h3>' + "".join(f"<p>{i}</p>" for i in items) + "</div>"
bugs = "".join(f"<tr><td>{Q(a)}</td><td>{Q(b)}</td></tr>" for a, b in cfg["dev_bugs"])
nums = "".join(f"<tr><td>{Q(a)}</td><td>{Q(b)}</td><td>{Q(c)}</td></tr>" for a, b, c in cfg["dev_numbers"])
harness = "".join(f"<li>{Q(h)}</li>" for h in cfg["dev_harness"])
lat_rows = "".join(f"<tr><td>{k}</td><td>{v[0]}</td><td>{v[1]}</td><td>{v[2]}</td></tr>"
                   for k, v in [("Answered", lats("success")), ("Partial", lats("marginal")),
                                ("No data", lats("no_data")), ("Asked a follow-up / no answer", lats("clarify"))])
fix = "".join(f"<li>{Q(f)}</li>" for f in cfg["dev_fix"])
works = "\n".join(f"      <li>{w}</li>" for w in cfg["works"])

page = (HTML_PAGE
        .replace("__TITLE__", Q(cfg["title"]))
        .replace("__H1__", Q(cfg["title"]))
        .replace("__SUB__", Q(cfg["subtitle"]).replace("&amp;", "&amp;"))
        .replace("__VERDICT__", cfg["verdict"])
        .replace("__SCORECARD__", score)
        .replace("__WORKS__", works)
        .replace("__GORES__", gores)
        .replace("__GOODQ__", Q(goodq))
        .replace("__GOODQI__", str(cfg["good"]["q"]))
        .replace("__GOODACT__", good_block)
        .replace("__GOODNOTE__", cfg["good"]["preamble"])
        .replace("__IDEAL__", cfg["good"]["ideal"])
        .replace("__IDEALNOTE__", cfg["good"]["ideal_note"])
        .replace("__OPTS__", opts).replace("__ROWS__", exp_rows)
        .replace("__FAILMAP__", fm).replace("__BUGS__", bugs)
        .replace("__NUMS__", nums).replace("__NUMSNOTE__", cfg["dev_numbers_note"])
        .replace("__HARNESS__", harness).replace("__LAT__", lat_rows)
        .replace("__LATNOTE__", cfg["latency_note"])
        .replace("__FIX__", fix)
        .replace("__FOOTER__", cfg["footer_score"])
        .replace("__RAWIDX__", raw_idx_html)
        .replace("__RAW__", raw_html)
        .replace("__ACCOUNT__", ACCOUNT).replace("__RUN__", str(RUN))
        .replace("__FILE__", f"query_results_v{RUN}.jsonl").replace("__N__", str(N)))

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(page)
print(f"WROTE {OUT} ({len(page)} bytes, {N} records, scorecard "
      + " ".join(f"{k}={v}" for k, v in sorted(by_outcome.items())))
