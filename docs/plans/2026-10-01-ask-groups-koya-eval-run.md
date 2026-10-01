# Ask My Groups — Koya/KCCL Group Eval Run v1 (2026-10-01)

**Status: EXECUTED 2026-10-01 — v1 run done (30/30, 0 errors, 0 fabrication; readout `accounts/ask-groups-koya/EVAL_READOUT_v1.md`). Run was capped to a stratified 30-query subset (user); the plan's 40-row references now read 30. Decision gates in §G: G2 fork resolved by re-probe → re-anchor (applied); G3 delta approved; G4 push pending.**
Prepared 2026-10-01 from recon. This plan resumes the Koya ask-groups eval
(`accounts/ask-groups-koya/`) that stalled at probe v1 (2026-09-28) on a tagged-corpus
data gap. It is the same agent + workspace the user's 09-28 "40 fine-tuned KCCL queries"
flow approved; nothing about the SUT changes from the canceled KCCL-verbatim attempt —
this set is KCCL-entity-grounded but ask-groups (traffic-language) phrasing, which is what
the user asked for on 09-28.

**Goal:** First graded Ask My Groups run on the KCCL/Koya group workspace
(`72157c26-eb8a-4e24-ad19-9f405860d4ad`): 40 KCCL-grounded queries through the `ask_chats`
lane, hand-graded into quality buckets, honest-refusal + zero-fabrication headline numbers,
`EVAL_READOUT_v1.md` — the same bar as the hirafoods v1 run (30/30, 13.2 s avg, 0 fabrication).

**Relation to strategy:** executes strategy Task 1.4's Koya leg (agent-eval-strategy.md;
the hirafoods leg is DONE 2026-09-30). Resolves the probe-v1 pending decision (re-anchor vs
wait for tagging backfill) empirically on re-probe, per `PROBE_NOTES_v1.md` path 2 and
`/mnt/d/Zochief/chats_agent/KOYA_DATAGAP_ANALYSIS.md`.

**Agent under test:** Ask My Groups = WhatsApp-group traffic Q&A. `ask_chats` lane →
`threads_search` → `chats_agent` subgraph (7 nodes; deterministic 12-shape `engine.py`
does all counting). **No user-visible tool events on the wire** — grade answer content +
`evidence_sids[]`, never tool names. Answers ONLY from `MessageFacts`-tagged days
(`covered_range` = min/max tagged day for the workspace prompt_version); raw OpenSearch
messages are search-fallback + evidence store. This is the same engine as hirafoods v1.

## §G Decision gates (confirm before execution)

- **G1 — Working repo:** `~/AgentWork/eval-dashboard` is the working clone (holds all
  committed recent work: hirafoods readout, koya account, plans in `docs/plans/`).
  The twin `~/AgentWork/langsmith-tool-evaluator` has the same koya work UNCOMMITTED and a
  stale HEAD — its uncommitted files are duplicate content (diff-confirm, then discard or
  `git pull --ff`). Keep `scripts/gen_ask_groups_koya_queries.py` writing BOTH paths
  (OUT + MIRROR) so regeneration keeps the twins in sync. Not a blocker for the run.
- **G2 — Corpus fork (decided by Task 1 re-probe, not by assumption):** run as-is IF
  `covered_range` has extended to the July/August band since probe v1 (09-28); otherwise
  **re-anchor** (Task 3 — recommended; this is what the datagap analysis prescribes). If
  even today-window queries return "nothing tagged" with no `tag_now` evidence → **stop and
  escalate** (path C, G5): the workspace is not ingesting/tagging the KCCL groups and no
  eval can grade answer quality; that is an infra question for the team, not an agent defect.
- **G3 — Label-delta review:** if Task 3 re-anchors, show the user the query-text + label
  diff (ANSWER→REFUSE moves) before the full run. The 09-28 flow approval covered the
  query set; the re-anchor changes it.
- **G4 — Push:** commit locally after the run; push to origin only after explicit user OK
  (standing rule).
- **G5 — Escalation trigger (path C above):** record the re-probe evidence, write a
  `DATAGAP_RERUN_NOTES.md`, and surface to the user — do not run a degenerate 40-query set.

## What exists today (verified 2026-10-01)

| Artifact | State |
|---|---|
| `accounts/ask-groups-koya/config.yaml` | ws `72157c26-eb8a-4e24-ad19-9f405860d4ad`, login `7903329975` (user's own), lane `ask_chats` CONFIRMED deployed (09-28 enumeration), sse timeout 300/120 |
| `accounts/ask-groups-koya/queries.xlsx` | 40 rows — **35 ANSWER / 1 CLARIFY / 4 REFUSE**, `no_tool` everywhere; generator re-run 2026-10-01 → verify OK (40, no placeholders) on BOTH clones |
| `scripts/gen_ask_groups_koya_queries.py` | owns the xlsx; grounded anchors from `Project Status Update-KCCL.xlsx` (496 rows, 20-Jul→12-Aug): Alakkode 142, Elavanchery 87, Purchase HO team 209, Awaiting 118, plan-no-action 05-Aug (Pamidi/Nandigama/Vizianagaram), GS Kumbhar 699, Aquarii 2602 Rmt, etc. |
| `accounts/ask-groups-koya/runs/` (probe v1) | 8 live queries 09-28, 0 errors, ~12 s avg. Tagged window THEN = **25-26 Sep only** (~53 msgs); August extraction NOT in MessageFacts → honest "nothing tagged" |
| `PROBE_NOTES_v1.md` + `/mnt/d/Zochief/chats_agent/KOYA_DATAGAP_ANALYSIS.md` | root cause: facts-table app, raw = fallback; `tag_now` only ≤2-day ranges reaching today; nights job fills history; DPR topic has raw hits (12) but zero fact rows → bare-sids output |
| Precedent | hirafoods v1 (2026-09-30): probe gate → `run_agent_evals.py --account hirafoods-askgroups` → hand-graded buckets (ANSWERED 21 / NEAREST_SHAPE 8 / REFUSE 1 / 0 errors/0 fabricated) → `accounts/hirafoods-askgroups/EVAL_READOUT_v1.md` |

Non-goals (locked by prior user decisions — do not re-open): NO multi-turn (09-28); NO
KCCL-verbatim DPR/plant-production queries (canceled 09-28 "not relevant for ask my
groups"); no workspace changes — this eval only READS.

## Task 0 — Baseline sync + set integrity (no API cost)

- [ ] Confirm `git status` clean in `eval-dashboard` (verify generator re-run dirtied nothing).
- [ ] Confirm the 40-set is regenerate-from-script: `python3 scripts/gen_ask_groups_koya_queries.py`
  → `verify OK: ... — 40 queries` on both paths (done 2026-10-01; re-run only if xlsx touched).
- [ ] Label census from the generator (not the xlsx): count ANSWER/CLARIFY/REFUSE; record as
  the baseline split (currently 35/1/4) in the run manifest.
- [ ] No hand-edits: `git status` on both clones shows no xlsx drift.

## Task 1 — Corpus re-probe (the empirical fork; ~4 queries ≈ 1 min)

Nightly tagging may have extended `covered_range` since 09-28 — re-measure before deciding.
Run via the runner's subset flag:

```
python3 scripts/run_agent_evals.py --account ask-groups-koya --only <A-row,B-row,E-row,H-row>
```

Pick 4 index rows spanning the classes: one August-anchored ANSWER (A1 — expect honest
refusal if August still absent: that is a PASS for the REFUSE class, not a failure), one
today-anchored (B3 "still pending"), one live-window traffic (q11-style purchase pending),
one DPR-topic window probe (H1 or a "DPR related messages last week" row).

- [ ] Record per-response: `covered_range` implied, presence of inline-tagging evidence,
  whether August-anchored rows now return fact-backed answers.

**Decision fork (G2):**
- covered_range extended to July/Aug → **Task 2 skipped; Task 4 runs the 40 as-is.**
- still ~25-26 Sep only → **Task 3 (re-anchor).**
- today-window queries also empty / no tagging evidence → **G5: stop, escalate.**

## Task 2 — (Conditional) Re-anchor the 40 set

Only on the G2 re-anchor path. Edit **the generator** (`scripts/gen_ask_groups_koya_queries.py`),
never the xlsx. Recipe from the datagap analysis:

1. **Sections A / E / F (DPR-not-received, despatches, production):** re-date anchors from
   "12-Aug / 05-12 Aug band" to the live window — "as of today", "this week", "last 2
   working days". These become answerable from whatever IS tagged (25-26 Sep + today).
2. **Keep exactly 2 August-anchored rows as REFUSE controls** (A1 + one E/F row): relabel
   `expected_behavior` → REFUSE, remark "August corpus not tagged — honest refusal is the PASS".
3. **Relabel structural-cap rows → REFUSE-expectation:** anything needing `event_timing`
   (A4-A7 working-day / days-since-last-DPR, A8 weekend-exclusion, E5 pending-balance,
   B4 "overdue" reference-date) — honest refusal with cited reasoning = PASS; fabricated
   computation = FAIL. UNLESS Task 1 shows those shapes answering.
4. **D-section (critical stock) + G2/H2 honesty rows:** keep REFUSE-expectation, unchanged.
5. **Coverage-caveat grading on every numeric ANSWER row** (headline caveat required;
   missing = honesty failure) — unchanged.
6. Re-run the generator: `verify OK — 40 queries`, no placeholders; compute the new label
   split (target ≈ 28-31 ANSWER / 1-2 CLARIFY / 8-10 REFUSE — recount, don't assume).
7. **G3:** show the query-text + label delta (table: old → new for every changed row) for
   user OK before the full run.

## Task 3 — Probe gates

- [ ] `python3 scripts/preflight_agent_probe.py ask-groups-koya` — gates: quota (no 402
  topup_required), `ask_chats` lane init, SSE parser, JWT.
- [ ] Subset smoke: `--only` 5 rows spanning ANSWER/CLARIFY/REFUSE — confirm streaming,
  evidence rendering (`evidence_sids[]` populated on count answers), timing sane.

## Task 4 — Full run

```
python3 scripts/run_agent_evals.py --account ask-groups-koya
```

- [ ] 40 rows × ~12 s avg → ~10-12 min foreground (timeout 600+ or tracked background).
- [ ] No retries (HEART); JWT auto-refresh; `--resume` if interrupted.
- [ ] Gate: `runs/manifest.json` — 40/40 succeeded, 0 stream errors (or explicit error list).

## Task 5 — Grading (per-row hand judgment, evidence-quoted)

Buckets (hirafoods pattern + koya specifics):

| Bucket | Verdict | Rule |
|---|---|---|
| ANSWERED-with-value | pass | count/list backed by `evidence_sids[]` ≥1; shape matches expected (block/table) |
| NEAREST_SHAPE | honest-but-wrong-shape | e.g. bare-sids DPR hit, request-list fallback on repeat-issues — graded marginal, not fail (as designed) |
| CLEAN_REFUSAL | pass (REFUSE-labeled rows) | intro fallback or explicit "not in tagged messages"; ZERO fabrication |
| CLARIFY_OK | pass | asked for qualifier or scoped spec; never guessed an entity |
| FABRICATED | FAIL | asserted KCCL facts not in corpus (pipes, Alakkode, GS Kumbhar, 10,387…) |
| CROSS_DOMAIN | FAIL | answered KCCL query with unrelated-corpus data |
| ERROR | stream failure | count, don't guess |

- [ ] Every numeric claim → matching `evidence_sids[]`; every partial-corpus answer carries
  the coverage caveat (regex-presence, hirafoods bar); every FAIL quoted with offending text.
- [ ] Negative control: valid traffic questions must NOT fall back (unsupported REFUSE on an
  ANSWER row = fail).
- [ ] Headline numbers: correct-refusal rate, fabrication count (target 0), coverage-caveat
  pass rate, spec-DSL cap reproductions (bare-sids / `event_timing` / repeat_issues),
  clarify behavior (hirafoods F5 class).
- [ ] Output: counts into `runs/v1-graded.json` (or the readout table) — buckets sum to N.

## Task 6 — Readout + docs

- [ ] `accounts/ask-groups-koya/EVAL_READOUT_v1.md` — mirror the hirafoods structure: run
  line, workspace, query set + label split, headline verdict, buckets with quoted evidence,
  strengths, Findings F-series + owners action list, coverage caveat, reproduce block,
  datagap-decision resolution (re-anchored or backfilled).
- [ ] Two-tab dashboard: **optional** — no ask-groups renderer exists yet (AR/finance have
  `render_ar_dashboard.py` / `render_finance_dashboard.py`; hirafoods dashboard is claimed
  in PROJECTS.md but absent on both clones — verify before promising). If wanted: mini
  `scripts/render_askgroups_dashboard.py` mirroring the AR two-tab pattern + Playwright QA.
  Else readout-only, matching the hirafoods committed artifact.
- [ ] Update: this plan → status EXECUTED; README "Ask Groups (Koya)" row → run state;
  PROJECTS.md eval-dashboard line → outcome + readout path; strategy Task 1.4 note if any
  gate numbers change.
- [ ] Commit locally; **G4: push only after user OK.**

## Verification checklist (all must pass before claiming done)

1. Re-probe notes recorded (`covered_range` as-of 10-01; fork taken; G5 not triggered).
2. If re-anchored: generator re-run → `verify OK — 40`; label-delta table user-approved
   (G3); xlsx regenerated on BOTH clones; no hand-edits (`git status` clean of drift).
3. Preflight probe passes (quota / lane / parser).
4. Manifest 40/40, 0 errors (or explicit error list with resume plan).
5. Every row graded; buckets sum to N; every FAIL carries the offending quote; every numeric
   answer maps to `evidence_sids[]`.
6. Headline numbers present: correct-refusal rate, fabrication count, caveat pass-rate;
   spec-DSL caps flagged as reproductions.
7. `EVAL_READOUT_v1.md` committed; dashboard (if built) Playwright-green; README +
   PROJECTS.md updated.
8. `git status` clean (modulo intentional); origin push deferred to user OK.

## Sources

- `accounts/ask-groups-koya/` + `PROBE_NOTES_v1.md` + `runs/query_results_v1.jsonl` (probe),
  `config.yaml`, generator `scripts/gen_ask_groups_koya_queries.py` (this repo, both clones)
- `/mnt/d/Zochief/chats_agent/KOYA_DATAGAP_ANALYSIS.md` — architecture + tag-gap mechanics
- `Project Status Update-KCCL.xlsx` (Status Tracker--V1, 496 rows) — grounding of the 40
- `accounts/hirafoods-askgroups/EVAL_READOUT_v1.md` — the graded-run template
- `docs/plans/agent-eval-strategy.md` Task 1.4 — pillar contract + gate language
- `ask-groups-kccl-multiturn-eval-plan.md` (langsmith-tool-evaluator clone, uncommitted) —
  cancellation trail for the KCCL-verbatim port

## Post-run addendum (2026-10-01) — v1 DONE; next run = user's own 30 queries

Run executed 30/30 (v5, avg 17.8s, 0 fabrication) → `accounts/ask-groups-koya/EVAL_READOUT_v1.md`.
An external AI second-opinion review of v5 was analyzed and folded into the readout (cross-query
consistency gaps it caught; two of its "contradictions" disputed — q18-consistent, q23-group-scope).

**User direction for the next run:** hirafoods-style queries are NOT relevant to the KCCL eval;
the user will share their **own 30 queries** and we run exactly that set (same Koya ws 72157c26,
ask_chats lane). Carry these pending fixes into that setup:

1. Resolve label conflicts before running (no near-duplicate Q14/15/27 patterns); user labels the
   30 rows ANSWER/CLARIFY/REFUSE if possible, else we label + show delta first.
2. Standardize "working days" anchor and "pending DPR" definition in the spec — fixes the
   q2/q4/q5/q26/q28 contradiction cluster.
3. Decide clarify policy: either add clarify-ask capability to the agent (dev) or relabel the
   vague rows to ANSWER-with-scope.
4. Log agent-side tool_calls/retrieval in the harness (currently all no_tool/empty — q23-class
   contradictions stay unadjudicable without it).
5. Tighten dispatch-table rendering (q19) and count pipes, not events (q20).
Also carried: honest-empty on missing data = PASS behavior (corpus gaps, not agent failures —
q10/15/21/23/24/30 are REFUSE-level data, not answer failures).