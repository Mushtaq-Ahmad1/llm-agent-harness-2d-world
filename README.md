# LLM Agent Harness — 2D Escape Room

A scaffolded environment for testing LLM agents on a multi-room escape puzzle. The agent perceives a 2D grid through text observations, reasons about which puzzle to solve next, and acts via tool calls.

The harness was designed to be small enough to read in a sitting, but rich enough to surface real LLM failure modes — and several were surfaced.
S
## Demo

Three short clips, one per model, showing the agent attempting the puzzle:

- [Claude Haiku 4.5 (60s)](docs/Haiku_run.mp4)
- [Claude Sonnet 4.5 (90s)](docs/Sonnet_run.mp4)
- [Claude Opus 4.7 (90s)](docs/Opus_run.mp4)

Each clip is sped up roughly 8× for watchability. The full text logs of each run are in [`logs/`](logs/).

## Quick start

You will need Python 3.10+ and an Anthropic API key.

```bash
# 1. Clone
git clone https://github.com/Mushtaq-Ahmad1/llm-agent-harness-2d-world.git
cd llm-agent-harness-2d-world

# 2. Install
pip install -r requirements.txt

# 3. Add your API key
#    Create a file called .env in the project root containing:
#    ANTHROPIC_API_KEY=sk-ant-...
#    The .env file is gitignored and will not be committed.

# 4a. Run headless (saves agent run to a log file)
python run_agent.py claude-sonnet-4-5 > logs/my_run.txt 2>&1

# 4b. Or run the browser UI (watch the agent live)
python server.py
# then open http://127.0.0.1:5000
```

The browser UI exposes a dropdown to switch between Claude Haiku 4.5, Sonnet 4.5, and Opus 4.7 without editing code. Pressing "Run Until Done" steps the agent forward until it solves the puzzle or hits the 100-step cap.

Reasonable cost per full run, current Anthropic pricing:

| Model      | Cost per 100-turn run |
|------------|-----------------------|
| Haiku 4.5  | ~£0.40                |
| Sonnet 4.5 | ~£1.50                |
| Opus 4.7   | ~£2.20                |