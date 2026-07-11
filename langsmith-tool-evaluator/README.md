# LangSmith Tool-Selection Evaluator

Evaluate whether your AI agent selected the **correct tool** for each user query in a LangSmith project.

Supports **past traces** (all existing runs in a project) and **future traces** (continuous polling for new runs).

Uses an **LLM Judge** (via [OpenCode](https://opencode.ai)) to score each tool selection on a 0.00–1.00 scale, then uploads results as LangSmith feedback and/or experiments.

**Live Dashboard**: https://navneetlearns.github.io/langsmith-tool-evaluator/

## Two Evaluation Modes

### Mode 1: LangSmith Traces (Legacy)
Pulls runs from a LangSmith project, parses tool calls from trace data, and scores each tool selection via the LLM judge. Requires a LangSmith API key with traced runs.

### Mode 2: Direct Copilot API Pipeline (Current)
Calls the ZoTok Copilot API directly — sends 50 user queries from the Surana Polycot test suite, captures SSE responses, and records tool calls + timing. Follows HEART.md principles (no retry, patient SSE timeout, response time tracking, versioned reruns).

**Run v1** (July 11, 2026): 50 queries | 49 success | 1 failed | avg 25.1s | 0 phantom tools

Results: `runs/query_results_v1.jsonl` | Manifest: `runs/manifest.json`

## Architecture

```
                         ┌─────────────────────┐
User Query ──► LLM Judge ──► Score + Reason ──►│ LangSmith Feedback  │
                    ▲                          │   (per-run)         │
                    │                          ├─────────────────────┤
              Tool Registry                    │ LangSmith Experiment│
         (registry/tool_registry.md)           │ (Datasets & Testing)│
                                               └─────────────────────┘
```

The judge performs **structured reasoning** — it reads the registry, identifies candidate tools, eliminates mismatches, and only then compares with the selected tool.

## Requirements

- Python 3.11+
- A LangSmith project with traced runs
- An OpenCode API key (or any OpenAI-compatible LLM endpoint)

## Project Structure

```
langsmith-tool-evaluator/                   # Git root: navneetlearns/langsmith-tool-evaluator
├── docs/
│   └── index.html              # Interactive eval dashboard (GitHub Pages)
├── runs/
│   ├── query_results_v1.jsonl  # Run v1 raw results (50 records)
│   └── manifest.json           # Versioned run manifest
├── evaluate_project.py          # CLI entry point (LangSmith mode)
├── evaluators/
│   ├── tool_selection.py        # Per-run feedback evaluator
│   ├── experiment.py            # LangSmith experiment runner
│   └── prompt_builder.py        # Tool registry parser + prompt builder
├── utils/
│   ├── langsmith_client.py      # LangSmith connection + paginated reader
│   ├── opencode_client.py       # OpenCode API wrapper (with JSON retry)
│   └── trace_parser.py          # Run parser (handles 4+ message formats)
├── prompts/
│   └── tool_selection_prompt.txt # 7-step structured reasoning prompt
├── registry/
│   └── tool_registry.md         # Tool definitions (edit to change toolset)
├── requirements.txt
└── .env.example

# Parent directory (not in repo):
../copilot_query_pipeline.py     # Direct Copilot API pipeline (auto-OTP, SSE parser)
../HEART.md                      # Eval testing principles (6 rules)
../eval_plan.md                  # Full knowledge doc + implementation plan
../runs/                         # Working directory for pipeline outputs
```

## Installation

```bash
cd langsmith-tool-evaluator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `LANGSMITH_API_KEY` | LangSmith API key |
| `LANGSMITH_ENDPOINT` | LangSmith endpoint URL (Cloud or self-hosted) |
| `LANGSMITH_PROJECT_NAME` | Project containing the runs to evaluate (default: `seller-copilot-agent`) |
| `OPENCODE_API_KEY` | OpenCode API key |
| `OPENCODE_BASE_URL` | OpenCode API base URL (e.g. `https://opencode.ai/zen/go/v1`) |
| `MODEL_NAME` | Model to use (default: `deepseek-v4-flash`) |

## Usage

### Basic — evaluate all past tool runs

```bash
# Evaluate ALL tool runs in the project (no limit)
python evaluate_project.py

# Evaluate last 100 tool runs
python evaluate_project.py --limit 100
```

### Time-filtered — evaluate runs since a date

```bash
# Since a specific date
python evaluate_project.py --since 2026-07-01

# Since an ISO datetime
python evaluate_project.py --since "2026-07-01T00:00:00"

# Relative: last 7 days
python evaluate_project.py --since 7d

# Relative: last 24 hours
python evaluate_project.py --since 24h
```

### Experiment mode — results visible in LangSmith UI

For results to appear in the **Datasets & Testing → Experiments** section:

```bash
# All past tool runs as an experiment
python evaluate_project.py --experiment --limit 0

# Last 7 days as an experiment
python evaluate_project.py --experiment --since 7d
```

An experiment creates/updates a dataset called `tool-selection-evaluator` and runs
`langsmith.evaluate()` to produce a tracked experiment. Open the URL printed
in the output to view results in the UI.

### Watch mode — continuously evaluate future traces

```bash
# Poll for new tool runs every 5 minutes
python evaluate_project.py --watch

# Custom poll interval (every 10 minutes)
python evaluate_project.py --watch --watch-interval 600

# Watch + experiment mode
python evaluate_project.py --watch --experiment
```

Watch mode keeps track of already-evaluated run IDs in memory and only processes
new runs on each poll cycle. Runs forever until interrupted (Ctrl+C).

### Other options

```bash
# Override project on the CLI
python evaluate_project.py --project "my-other-project"

# Evaluate chain runs instead of tool runs
python evaluate_project.py --run-type chain --limit 50

# Override model
python evaluate_project.py --model "gpt-4o"

# Debug logging
python evaluate_project.py --verbose
```

## How It Works

1. **Connect** — Authenticates to LangSmith and OpenCode via `.env`.
2. **Fetch runs** — Reads runs from the LangSmith project with pagination, optionally filtered by `--since` and `--run-type`.
3. **Parse traces** — Extracts the user query, tool calls, tool arguments, and final answer from each run using 6 extraction strategies (handles LangChain serialized messages, OpenAI role-based format, tool-run-native format, evaluator format, and more).
4. **Build prompt** — Constructs a structured 7-step evaluation prompt with the tool registry, user query, and selected tool.
5. **LLM Judge** — Sends the prompt to OpenCode with `temperature=0`.
6. **Score** — The judge returns JSON with `expected_tool`, `score`, `reason`, and `candidate_tools`.
7. **Upload** — Scores are uploaded as LangSmith feedback (`tool_selection` key) and optionally as a tracked experiment.

### What gets skipped

The evaluator automatically skips runs where:
- The extracted query looks like a system prompt (detected by content patterns or length >500 chars)
- No user query was found
- The tool calls came from tool *definitions* rather than actual invocations
- The run has no ID

## Tool Registry

The registry at `registry/tool_registry.md` defines the available tools. Each entry has:

| Column | Description |
|---|---|
| **Tool** | Unique tool identifier |
| **Family** | Functional group (e.g. `conversation_read`) |
| **Enabled** | ✅ if the tool is currently active |
| **Description** | What the tool does — the judge uses ONLY this to evaluate |

To evaluate a different toolset, just edit this file. **Never hardcode tools in Python.**

## Scoring Rubric

| Score | Meaning |
|---|---|
| **1.00** | Perfect match — exactly the right tool |
| **0.75** | Usable, but another tool is more appropriate |
| **0.50** | Partially relevant — can contribute but not primary |
| **0.25** | Weak match — barely related |
| **0.00** | Wrong tool — completely unrelated |

If the user query is a greeting or chit-chat that requires no tool, the expected tool is `"none"` and score is `1.00` when no tool was selected.

## Output Examples

### Feedback mode

```
2026-07-09 12:40:06 | INFO | Run=019f46da Query=Which customer has highest total number
             Tool=getCustomerAccountData  Expected=none  Score=0.00  Elapsed=38.05s
2026-07-09 12:40:33 | INFO | Run=019f46d6 Query=Which customer has ordered the highest t
             Tool=getCustomerAnalytics    Expected=none  Score=0.00  Elapsed=9.98s

====================================================================
  EVALUATION SUMMARY
====================================================================
  Total runs seen:   5
  Evaluated:         3
  Failed:            0
  Skipped:           2
====================================================================
```

### Experiment mode

```
✅ Experiment created!
   Open in browser: https://smith.langchain.com/datasets/<uuid>/experiments
```

## Error Handling

- If the OpenCode API call fails → the run is marked as **Failed** and evaluation continues.
- If JSON parsing fails → one automatic retry, then the run is **Failed**.
- If a run has no user query → it is **Skipped**.
- If a run has no tool calls → the selected tool is `"none"`.
- The evaluator **never stops** on a single failure.
- In watch mode, a failed poll cycle doesn't crash the watcher — it logs and retries on the next cycle.

## Trace Parser — Field Mapping

The parser handles these real-world LangSmith run formats:

| Run Type | Query Location | Tool Name | Tool Arguments |
|---|---|---|---|
| **Tool run** | `extra.metadata.title` | `run.name` | `inputs` dict |
| **Chain run** | `inputs.messages[].content` | child `tool` runs' names | child run `inputs` |
| **LLM run** | `inputs.messages[].content` | `generations[].kwargs.tool_calls` | `function.arguments` |
| **Evaluator run** | `inputs.input.messages[].content` | `inputs.output.messages[].tool_calls` | `tool_calls[].args` |

## Multiprocessing (Future)

The evaluator currently processes runs sequentially. The code is structured so that adding multiprocessing requires only wrapping the `_evaluate_single` call in a `concurrent.futures.ThreadPoolExecutor` or `ProcessPoolExecutor` — no architectural changes needed.

## Future Evaluations

### Multi-turn Conversation Evaluation

The current evaluator treats each run as an isolated (query → tool) pair. A multi-turn evaluator
would assess tool selection across an entire conversation trace by:

- Grouping runs by `trace_id` or `thread_id` (all runs belonging to the same conversation)
- Reconstructing the full message history and tool-call sequence
- Evaluating whether the tool choice at each turn is correct **given the conversation context**
  (previous tool results, earlier decisions, evolving user intent)
- Detecting issues like redundant tool calls, missed follow-up steps, or contradictory tools

Implementation sketch:
```
1. Fetch all runs grouped by trace_id → conversation
2. For each conversation, walk messages in order
3. At each AI message with tool_calls, evaluate:
   - Is this the right tool given the conversation so far?
   - Are the arguments consistent with previous tool results?
   - Is the order of tool calls logical?
4. Score each turn independently, then aggregate per-conversation
```

Relevant data sources:
- `trace_id` on each run (groups runs into conversations)
- `inputs.messages` on chain runs (full message history at each step)
- `extra.metadata.thread_id` / `langfuse_session_id` (thread-level identifiers)

### Final Response / Format-Node Evaluation

This eval would assess the **quality and structure of the agent's final output**, not the tools it
chose to get there. It would evaluate:

- **Format compliance**: Does the response match the expected schema (JSON structure,
  required fields, data types)?
- **Content correctness**: Does the response accurately reflect the tool results it received?
- **Completeness**: Does the answer address all parts of the user's query?
- **Hallucination detection**: Does the response fabricate data not present in the tool results?
- **Response structure**: For structured outputs (suggestions, resolved_tool_call_ids, etc.),
  does the format follow the expected pattern?

Implementation sketch:
```
1. For chain runs that produced a final response:
2. Extract: user query, final answer, all tool results from the trace
3. Build a prompt that asks the judge to evaluate:
   - Is the final answer well-formatted?
   - Does it correctly use the tool results?
   - Does it address the user query completely?
   - Are there any hallucinations or contradictions?
4. Score each dimension separately, with an overall composite score
```

Relevant data sources:
- Last AI message's `content` in `inputs.output.messages` (evaluator format)
- `outputs.output.content` on tool runs (raw tool results)
- `outputs` on chain runs (the final output dict)
- Tool result `content` fields for cross-referencing
