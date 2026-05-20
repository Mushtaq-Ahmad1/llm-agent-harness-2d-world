# LLM Agent Harness — 2D Grid Escape Room

A harness that places an LLM agent into a 2D grid world where it perceives its environment, reasons about its state, and takes actions to accomplish goal-directed tasks. The world is a three-room escape room with three distinct puzzle mechanics; the agent must read clues, manipulate objects, and plan across rooms to reach the exit.

Built for the Humanoid Software Engineering Internship challenge.

## Demo

![Agent solving the escape room](docs/demo.gif)

A full transcript of a successful run is in [`logs/sonnet_demo_run.txt`](logs/sonnet_demo_run.txt).

## Quick start

```bash
git clone https://github.com/Mushtaq-Ahmad1/llm-agent-harness-2d-world
cd llm-agent-harness-2d-world

python -m venv .venv && source .venv/bin/activate    # on Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and add ANTHROPIC_API_KEY=sk-ant-...
```

**To play the world manually in a browser:**
```bash
python server.py
```
Open <http://localhost:5000>.

**To run the LLM agent headlessly:**
```bash
python run_agent.py                       # Sonnet (default, recommended)
python run_agent.py claude-haiku-4-5      # Haiku (cheaper, weaker)
```

The agent prints its reasoning and actions each turn and stops when it reaches the exit or after 100 turns.

## The world

A 14×22 grid divided into three rooms by locked doors:

- **Room 1** has a wall of 8 binary levers and a note explaining "set the levers to encode 170." It also contains one of the three boxes the agent will need later, and a secondary lever isolated from the main lever wall.
- **Room 2** has three coloured pressure plates and two more boxes. A separate note gives the mapping from box labels (revealed by inspecting) to plate colours.
- **Room 3** contains the exit, a yellow pressure plate, and notes describing a final mechanic.

Two additional design choices make the puzzle harder than the sum of its parts:

1. **Doors re-lock when their puzzle becomes unsolved.** Moving a correctly-placed box re-locks the door behind you. This forces the agent to plan around irreversibility.
2. **A safety lever in Room 1 permanently freezes the second door open**, but only after the agent has read the note in Room 3 explaining it. The full solution therefore requires walking back through earlier rooms — a real test of memory and global planning.

## How the harness works

Each turn:

1. The world state is rendered into a structured text **observation** containing: the agent's position, a small ASCII view, a list of nearby objects with their state, a "puzzle progress" section computed from ground-truth world state, the agent's inventory and scratchpad, recent events, and currently-legal actions.
2. The observation is sent to Claude via the Anthropic API with a system prompt and **tool-use definitions** for each available action (`move`, `move_path`, `flip`, `read`, `pick_up`, `drop`, `inspect`, `remember`).
3. Claude returns reasoning text plus a structured tool call. The harness applies the action to the world and the loop repeats.

There is no message history between turns — the agent's persistent memory is its own scratchpad (written via the `remember` tool) plus a sliding window of recent events. This keeps token cost flat regardless of run length.

## Architecture

```
agent-world/
├── server.py              # Flask backend serving GUI + world endpoints
├── run_agent.py           # Headless agent runner
├── run.py                 # Terminal-based manual playthrough (early dev tool)
├── src/
│   ├── world.py           # Grid, terrain, objects, action verbs
│   ├── levels.py          # Static world definition (three rooms)
│   ├── observation.py     # World state → text observation
│   ├── serialize.py       # World state → JSON for the GUI
│   └── agent.py           # LLM agent, tool definitions, system prompt
├── templates/index.html   # GUI layout
├── static/                # Canvas renderer + styles
└── logs/                  # Saved agent runs
```

A key design decision: **the GUI and the agent share the same world.** The GUI renders the same `World` object that the agent acts on, but they consume different representations of it. The browser receives JSON; the agent receives text. The two interfaces are completely decoupled.

## Design choices

### Observation representation

The observation is **structured text plus a small ASCII view**, not a screenshot of the GUI. Three reasons:

1. **LLMs are weaker at parsing game UIs from images than they are at parsing structured text.** Sending a screenshot would actively make the agent worse.
2. A text observation can include things the visual cannot easily convey: reachability from the agent's position (computed via BFS each turn), whether a box is correctly placed, exact coordinates of nearby objects.
3. It's vastly cheaper. A turn costs ~5,000 input tokens vs. far more for an image.

The observation has dedicated sections — `LOCAL VIEW`, `VISIBLE OBJECTS`, `BOXES IN VIEW`, `PUZZLE PROGRESS`, `DOOR STATUS`, `YOUR NOTES`, `RECENT EVENTS`, `AVAILABLE ACTIONS` — each addressing a specific failure mode I encountered during iteration. The `PUZZLE PROGRESS` section in particular is computed from ground-truth world state and tagged "trust this" — added after the agent kept second-guessing whether actions had succeeded.

### Action space

Eight discrete tools:
- `move(direction)` — single-cell movement
- `move_path(directions)` — up to 8 directions executed in sequence, halting on the first illegal move
- `flip(lever_id)`, `read(note_id)`, `pick_up(box_id)`, `drop(box_id)`, `inspect(box_id)` — direct interactions
- `remember(text)` — append to the agent's persistent scratchpad

The action space is **deliberately small**. Every observation also lists the actions currently legal from the agent's position with their exact argument values, so the agent never has to guess what's possible. `move_path` was added partway through development to cut API costs by ~3× during dev iteration — known routes shouldn't require a fresh API call per cell.

I used **tool use** rather than asking Claude to output free-text actions for the harness to parse. This makes the interface robust to phrasing and keeps the agent's reasoning text and chosen action cleanly separated in the response.

### Why a browser visualisation

The GUI is for the human, not the agent. It made manual playtesting fast, gave me a concrete way to debug puzzle mechanics independently of the agent, and made the demo recording possible. The agent gets its own representation; the two interfaces share a world but not a perception.

## What worked

- **One world, two interfaces.** Building the world as a self-contained Python module (with no view-layer dependencies) meant the GUI and the agent could be developed and debugged independently. The agent code never imports anything from the Flask side, and vice versa.
- **Tool use over text parsing.** Once defined as JSON schemas, the eight actions were trivially reliable. The agent never produced an unparseable action.
- **The PUZZLE PROGRESS section.** This was the single highest-impact change to the harness. Before it existed, the agent would solve a puzzle, walk away, then return and "verify" it by repeating actions — locking and unlocking doors in a loop. Once it could simply read `red plate: CORRECT`, the loops disappeared.
- **Reachability tags in the observation.** Widening the visible radius let the agent spot far-away objects, but introduced a new failure: the agent would try to interact with things behind locked doors. A simple BFS that tags each object with `[BLOCKED]` if no walking path exists fixed this entirely.

## What didn't work (and what I'd do next)

- **First-pass observation was too verbose.** Early versions of the prompt and observation pushed the agent into "groundhog day" — each turn it would re-derive the same facts because the previous turn's reasoning was lost. The fix was the `remember` tool plus a system-prompt rule emphasising that "anything you don't write down is gone next turn." Adding a `PUZZLE PROGRESS` ground-truth section in the observation also helped, because it gave the agent something authoritative to consult instead of trying to reason from scratch.
- **The repetition detector was brittle.** I added a "you have repeated this action 3+ times — stop" warning, but the agent learned to thrash between equivalent actions (pick up box → drop box → pick up box) that didn't trigger the exact-match detector. A second detector that counts interactions per *object* over a wider window catches this.
- **Haiku struggles where Sonnet handles it cleanly.** I iterated on the harness using Claude Haiku 4.5 for cost reasons. The harness improvements made Haiku noticeably more capable, but it still occasionally collapses on Level 3, which requires multi-step planning across rooms. Sonnet 4.5 completes the full puzzle. This is an interesting finding in itself: harness quality lets a weaker model get most of the way, but the hardest puzzles still demand a stronger model.
- **What I'd do next.** (a) Add a "summarise scratchpad" step every N turns to prevent staleness on longer runs. (b) Move from a fixed observation template to an attention-style mechanism where the agent can request more detail on a particular object. (c) Generalise the world so puzzles are data-driven, allowing procedural level generation.

## Example task and run

The default goal is "escape the room — reach the EXIT tile." A successful Sonnet run takes ~45 turns and proceeds:

```
Turn 6:  read note_levers   → "set levers to encode 170"
Turn 7:  remember           → "binary code is 170 = 10101010"
Turn 10: pick_up box_1
Turn 11: inspect box_1      → label C
…
Turn 26: flip lever_7       → door_1 unlocks
Turn 34: drop box_2         → red plate satisfied
Turn 39: drop box_3         → green plate satisfied
Turn 44: drop box_1         → blue plate satisfied; door_2 unlocks
…
Turn 55: read note_safety   → arms the safety lever
Turn 61: flip lever_safety  → second door now permanently open
Turn 67: pick_up box_3 from green plate
Turn 72: drop box_3 on yellow plate
Turn 73: step onto EXIT     → WIN
```

The full transcript with reasoning is in `logs/sonnet_demo_run.txt`.

## Limitations

- The world is hand-authored. There's no procedural generation, so the agent could in principle memorise solutions across runs (it doesn't, but it could).
- The agent has no concept of cost — it doesn't trade off action quality against API spend.
- The puzzles are designed; there's no scoring of optimality (a 30-turn solution and a 90-turn solution both count as wins).
- Image observations were deliberately excluded; the harness doesn't currently support multimodal models.