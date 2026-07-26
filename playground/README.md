# Playground Eval

Non-streaming REST eval pipeline for ZoTok WhatsApp bots. Tests welcome bots, intent bots, custom trigger action bots, and unknown bots without going through WhatsApp.

## Quick Start

```bash
# Install deps
pip install requests

# Run all scenarios
python3 playground_pipeline.py

# Run a specific bot
python3 playground_pipeline.py --scenario scenarios/mybot.json

# Quick mode — test default.json against a different workspace
python3 playground_pipeline.py --workspace <workspace-id>

# Disable multi-turn (fresh chat per query)
python3 playground_pipeline.py --no-chat-persistence

# Build dashboard
python3 build_dashboard.py
```

## Project Structure

```
playground-eval/
├── playground_pipeline.py    # Main test runner (CLI)
├── build_dashboard.py        # Dashboard builder
├── HEART.md                  # Principles
├── scenarios/
│   ├── default.json          # Kalavathi Traders test cases
│   └── <bot-name>.json       # Add one per custom bot
├── runs/
│   ├── results_{run_id}.jsonl# Versioned results (never overwritten)
│   └── manifest.json         # Run version tracker
└── docs/
    └── index.html            # Self-contained dashboard
```

## Adding a Bot

Create a new JSON file in `scenarios/`:

```json
{
  "bot_name": "My Bot",
  "workspace_id": "<workspace-uuid>",
  "customer_id": "<customer-uuid>",
  "test_cases": [
    {
      "id": "welcome",
      "query": "hi",
      "category": "Welcome",
      "expected": {
        "response_type": "interactive",
        "contains": ["connected"]
      }
    }
  ]
}
```

Run it with `python3 playground_pipeline.py --scenario scenarios/mybot.json`.

## API Reference

| Endpoint | `POST /hub/bot/api/v1/chat/preview` |
|----------|--------------------------------------|
| Base URL | `https://api-qa.zotok.ai` |
| Auth | None |
| Params | `sellerWorkspaceId`, `customerId`, `chatId` (optional) |
| Body | `{"message": "<query>"}` |
| Timeout | 30s |

## Deployment

The `docs/` folder is ready for GitHub Pages. Push to `main` and enable Pages from the `docs/` folder.

## HEART Principles

See [HEART.md](HEART.md) for the governing principles of this project.
