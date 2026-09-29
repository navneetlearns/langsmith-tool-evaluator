#!/usr/bin/env python3
"""Ask My Groups — Reflect node mechanism test (memory-only, no retry).

Per §3/§5/§6 of docs/plans/ask-groups-reflect-node-test-plan.md:
- SEED = real judged failure from existing run JSONLs (accounts/ask-groups* runs) — NOT re-fired.
- For each pair: Arm A (CONTROL) fires a NEW same-class query plain in a fresh thread;
  Arm B (MEMORY) fires the SAME query text with the lesson block prepended (load_context proxy).
- Writer = DETERMINISTIC TEMPLATE (no LLM: mapping failures are derivable from the wire record;
  fixed lesson text = zero sampling confound). nano-LLM writer is the dev-side upgrade.
- Judging happens AFTER the run per skill refs/ask-groups-agent.md (ANSWER/CLARIFY/REFUSE +
  evidence contract + honesty-caveat feature). This runner only captures raw records.

Usage:
  python3 scripts/reflect_ask_groups_test.py --gate     # 1 probe query per workspace (quota+lane)
  python3 scripts/reflect_ask_groups_test.py            # full paired run (fresh threads per arm)
  python3 scripts/reflect_ask_groups_test.py --resume 1 # skip arms already in v<N>
"""
import argparse, json, os, sys, time, uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from copilot_query_pipeline import (load_account_config, CopilotAuth, CopilotClient,
                                    get_next_version, load_manifest, save_manifest,
                                    update_manifest)

REF_DIR = Path(__file__).resolve().parent.parent / "accounts" / "ask-groups-reflect"
RUNS_DIR = REF_DIR / "runs"
BUFFER = REF_DIR / "memory_buffer.jsonl"

LESSON_INTRO = "[Workspace lesson (internal, do not quote to the customer)]: "

# --- Test set: SEED (existing judged failure) -> LESSON (deterministic) -> ARM query (new) ---
# F1: corpus-window mismatch (Koya) — seed q1: Aug DPR "19 of 19 not tagged yet, tagging runs overnight"
# F2: hollow where data exists (Koya) — seed q31: DPR hits, "not answerable... YouTube link + request to discuss"
# F3: action-ask REFUSE rephraseable (Zainab) — seed: recon cheque anchor "Chq leke gaya tha 2nd sept ko. Not deposited yet??"
# F4: alias->entity clarify-park (Zainab) — seed: recon alias list (Finesse Decor, Whistling Wood)
# F5: intro fallback despite data (Zainab) — seed q1: "How many groups do I have?" -> intro fallback
PAIRS = [
    {
        "cls": "F1", "account": "ask-groups-koya",
        "seed_ref": "koya v1 q1 (2026-09-28): 'Which projects haven't submitted their DPR on 12 August?' -> 19/19 untagged, tagging runs overnight",
        "lesson": ("August is NOT in the live tagged window. For any August-anchored question: "
                   "do not raw-search the period, state that August is not covered and answer "
                   "from the tagged subset with the coverage caveat."),
        "arm_query": "Which projects did not submit their DPR in August?",
    },
    {
        "cls": "F1b", "account": "ask-groups-koya",
        "seed_ref": "koya v1 q22 (2026-09-28): 'factory-wise raw material stock info in the last week' -> 59/59 in-window untagged",
        "lesson": ("A large share of in-window messages is still untagged (59/59 at probe time). "
                   "For coverage-heavy windows: hedge every number with the untagged %, cite the "
                   "tagged subset, and say the count will change as tagging lands."),
        "arm_query": "What raw material stock information was shared last week?",
    },
    {
        "cls": "F2", "account": "ask-groups-koya",
        "seed_ref": "koya v1 q31 (2026-09-28): 'factories produce per latest DPR' -> 'not answerable... YouTube link and a request to discuss'",
        "lesson": ("DPR-topic messages exist but no fact rows were extracted. When the evidence "
                   "is a bare ID or a non-fact message, fall back to LISTING the DPR-related "
                   "messages (request-list shape the spec supports) with the coverage caveat "
                   "instead of a bare not-answerable."),
        "arm_query": "List the latest DPR updates shared by the factories.",
    },
    {
        "cls": "F3", "account": "ask-groups",
        "seed_ref": "zainab recon (2026-09-23): 'Chq leke gaya tha 2nd sept ko. Not deposited yet??' — action/status ask answered from messages",
        "lesson": ("ask_chats answers QUESTIONS from messages; it cannot place calls or take "
                   "actions. Convert action asks into the equivalent evidence question ('what "
                   "was said about X') instead of refusing outright."),
        "arm_query": "Chase Vicky Jain about the cheque taken on 2nd September.",
    },
    {
        "cls": "F4", "account": "ask-groups",
        "seed_ref": "zainab recon aliases (2026-09-23): Finesse Decor / Whistling Wood / Casa walls as typed in groups",
        "lesson": ("Customers appear in groups as typed: 'Finesse Decor', 'Whistling Wood', "
                   "'Casa walls'. Resolve the alias against group names ('<Customer> + Zainab') "
                   "before asking for identity confirmation; do not force a generic clarify."),
        "arm_query": "What orders has Whistling Wood placed this week?",
    },
    {
        "cls": "F2b", "account": "ask-groups-koya",
        "seed_ref": "replication of F2 (same lesson family, different phrasing)",
        "lesson": ("DPR-topic messages exist but no fact rows were extracted. When the evidence "
                   "is a bare ID or a non-fact message, fall back to LISTING the DPR-related "
                   "messages (request-list shape the spec supports) with the coverage caveat "
                   "instead of a bare not-answerable."),
        "arm_query": "What have the factories shared about AMRUT 100 recently?",
    },
    {
        "cls": "F4b", "account": "ask-groups",
        "seed_ref": "replication of F4 (same lesson family, different alias)",
        "lesson": ("Customers appear in groups as typed: 'Finesse Decor', 'Whistling Wood', "
                   "'Casa walls'. Resolve the alias against group names ('<Customer> + Zainab') "
                   "before asking for identity confirmation; do not force a generic clarify."),
        "arm_query": "What has Finesse Decor ordered this month?",
    },
    {
        "cls": "F5", "account": "ask-groups",
        "seed_ref": "zainab recon v1 q1 (2026-09-23): 'How many groups do I have?' -> intro fallback despite 570-group parse memory",
        "lesson": ("The 570-group inventory sits in parse memory. For group-count questions use "
                   "the list/count shape over groups; do NOT return the intro fallback."),
        "arm_query": "How many of my groups are active?",
    },
]

JUDGE_RULES = ("graded post-run per skill refs/ask-groups-agent.md: behavior/evidence (no tool "
               "events), ANSWER/CLARIFY/REFUSE + evidence contract, honesty caveats = feature, "
               "capability gaps = NEAREST_SHAPE (not a fail), contradiction -> lesson yields.")


def write_buffer(rec):
    BUFFER.parent.mkdir(parents=True, exist_ok=True)
    with open(BUFFER, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def fire(client, thread_id, text):
    init_ok = client.init_thread(thread_id)
    if not init_ok:
        return {"response": "", "tool_calls": [], "status_sequence": [],
                "ui_payload_type": None, "suggestions": [], "response_time_seconds": 0,
                "error": "Thread init failed", "thread_id": thread_id}
    res = client.stream_query(thread_id, text)
    return {**res, "thread_id": thread_id}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", action="store_true",
                    help="quota+lane probe: 1 plain query per workspace, then exit")
    ap.add_argument("--resume", type=int, default=None, help="skip arms already in version N")
    args = ap.parse_args()

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    version = get_next_version(RUNS_DIR)
    out_file = RUNS_DIR / f"query_results_v{version}.jsonl"

    completed = {}
    if args.resume:
        rf = RUNS_DIR / f"query_results_v{args.resume}.jsonl"
        if rf.exists():
            for line in rf.read_text().splitlines():
                try:
                    r = json.loads(line)
                    completed[(r["cls"], r["arm"])] = r
                except Exception:
                    pass
            print(f"[reflect] resume: {len(completed)} arms loaded from v{args.resume}")

    pairs = PAIRS
    if args.gate:
        # one plain query per distinct workspace (quota + lane + parser sanity)
        gate_pairs, seen = [], set()
        for p in PAIRS:
            if p["account"] not in seen:
                seen.add(p["account"])
                gate_pairs.append({**p, "arm_query": "How many groups do I have?",
                                   "cls": p["account"]})
        pairs = gate_pairs
        print(f"[reflect] GATE: {len(pairs)} probe query(-ies)")

    clients = {}
    results = []
    for p in pairs:
        acc, cls = p["account"], p["cls"]
        if acc not in clients:
            cfg = load_account_config(acc)
            auth = CopilotAuth(cfg["phone"], cfg["base_url"]); auth.login()
            clients[acc] = (cfg, CopilotClient(auth, cfg))
            print(f"[reflect] {acc}: authenticated")
        cfg, client = clients[acc]

        for arm, text in (("A", p["arm_query"]),
                          ("B", f"{LESSON_INTRO}{p['lesson']}\n\n{p['arm_query']}")):
            if args.gate and arm == "B":
                continue  # gate = one plain query per workspace
            key = (cls, arm)
            if key in completed:
                results.append(completed[key])
                print(f"[reflect] {cls}/{arm} skipped (resume)")
                continue
            tid = str(uuid.uuid4())
            t0 = time.time()
            rec = fire(client, tid, text)
            rec.update({"cls": cls, "arm": arm, "account": acc,
                        "seed_ref": p["seed_ref"], "lesson": p["lesson"] if arm == "B" else None,
                        "query": p["arm_query"],
                        "response_time_seconds": rec.get("response_time_seconds")
                        or round(time.time() - t0, 2)})
            results.append(rec)
            with open(out_file, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            resp = (rec.get("response") or "")[:110].replace("\n", " ")
            print(f"[reflect] {cls}/{arm} {rec.get('response_time_seconds',0):6.1f}s "
                  f"err={str(rec.get('error'))[:40]} | {resp}")

        # lesson buffer: one row per pair (only in full run, not gate)
        if not args.gate:
            write_buffer({"cls": cls, "account": acc, "seed_ref": p["seed_ref"],
                          "lesson": p["lesson"], "verdict_seed": "judged-failure (existing run)",
                          "confidence": 0.9, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                          "expires_at": "2026-10-29"})

    if not args.gate:
        ok = sum(1 for r in results if not r.get("error") and (r.get("response") or "").strip())
        avg = sum(r.get("response_time_seconds", 0) for r in results) / max(len(results), 1)
        update_manifest(RUNS_DIR / "manifest.json", version, out_file,
                        len(results), ok, len(results) - ok, avg)
        print(f"[reflect] v{version} DONE: {ok}/{len(results)} streams ok, avg {avg:.1f}s "
              f"-> {out_file}\n{JUDGE_RULES}\nBuffer: {BUFFER}")
    else:
        print("[reflect] GATE DONE — inspect the two raw answers before the full run.")


if __name__ == "__main__":
    main()