"""
LLM agent. Talks to Claude via the Anthropic SDK.

Tool use, not text parsing: actions are defined as tool schemas and Claude
invokes them by name. Cleaner, more reliable, and the response naturally
contains both reasoning text and a structured action.
"""

import os
from anthropic import Anthropic
from dotenv import load_dotenv

from src.world import World
from src.observation import build_observation

load_dotenv()

SYSTEM_PROMPT = """You are an agent in a 2D grid escape room. Goal: step onto the EXIT tile.

The world has rooms separated by locked doors. Each door is gated by a puzzle, and clues are on notes in the rooms. Some puzzles RE-LOCK if their state is undone (e.g. removing a box from its plate).

Each turn you get an observation with: your position, what's around you, your scratchpad, recent events, and currently-legal actions. Call EXACTLY ONE action tool.

RULES (most important first):

1. THE OBSERVATION IS GROUND TRUTH. Your INVENTORY, POSITION, and PUZZLE PROGRESS sections are computed from the actual world state every turn. If your scratchpad says one thing and the observation says another, the OBSERVATION is correct and your scratchpad is stale. Use `remember` to write down NEW facts you've derived, never to record current state — that's already in the observation.

2. PICK UP UNPLACED BOXES. Boxes you see should be inspected and picked up — you may need them later and may not be able to return. Exception: leave boxes tagged [CORRECT — do not touch] where they are.

3. EXPLORE BEFORE SOLVING. Walk the room first to find notes, boxes, levers. Don't try to solve from clues you haven't gathered.

4. TRUST PUZZLE PROGRESS. The PUZZLE PROGRESS section is ground truth. Don't re-check what it says is correct. Don't re-read notes whose text is already in your scratchpad.

5. BATCH MOVES. Use `move_path` (up to 8 dirs) for known routes; each API call costs money. Use single `move` only when truly exploring.

6. RESPECT TAGS. [BLOCKED] = wall or locked door between you and the object; you can't reach it. [CORRECT — do not touch] = box is correctly placed and moving it re-locks a door; leave it. [CORRECT — safe to move] = you may pick it up.

7. LEVERS need same-cell standing — move onto the lever before flipping.

Be brief in reasoning. One or two sentences. Long reasoning is discarded between turns."""
# Tool definitions. Claude sees these and calls them by name with structured args.
TOOLS = [
    {
        "name": "move",
        "description": "Move one cell in a cardinal direction. Only legal directions will be available.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["north", "south", "east", "west"]}
            },
            "required": ["direction"],
        },
    },
    {
        "name": "move_path",
        "description": (
            "Move multiple cells in sequence. Use this when you have a clear path planned, "
            "to avoid wasting turns on individual moves. Provide a list of directions in order. "
            "Maximum 8 directions per call. Execution stops at the first illegal move and you "
            "get the current state back. Prefer this over single move() calls when traversing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "directions": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["north", "south", "east", "west"]},
                    "minItems": 1,
                    "maxItems": 8,
                }
            },
            "required": ["directions"],
        },
    },
    {
        "name": "flip",
        "description": "Flip a lever on your current cell. Lever IDs look like lever_0, lever_1, etc.",
        "input_schema": {
            "type": "object",
            "properties": {"lever_id": {"type": "string"}},
            "required": ["lever_id"],
        },
    },
    {
        "name": "read",
        "description": "Read a note on or adjacent to your current cell. Returns the note's text.",
        "input_schema": {
            "type": "object",
            "properties": {"note_id": {"type": "string"}},
            "required": ["note_id"],
        },
    },
    {
        "name": "pick_up",
        "description": "Pick up a box on or adjacent to your current cell. Adds it to your inventory.",
        "input_schema": {
            "type": "object",
            "properties": {"box_id": {"type": "string"}},
            "required": ["box_id"],
        },
    },
    {
        "name": "drop",
        "description": "Drop a box from your inventory onto your current cell.",
        "input_schema": {
            "type": "object",
            "properties": {"box_id": {"type": "string"}},
            "required": ["box_id"],
        },
    },
    {
        "name": "inspect",
        "description": "Inspect a box (in inventory or adjacent) to reveal its label. Labels are A, B, or C.",
        "input_schema": {
            "type": "object",
            "properties": {"box_id": {"type": "string"}},
            "required": ["box_id"],
        },
    },
    {
        "name": "remember",
        "description": "Write a SHORT note to your persistent scratchpad. Only record DERIVED facts (the binary code is 170, A→red B→green C→blue). Do NOT record current state like position or inventory — those are in every observation. Long notes become stale; one line per fact.",
        "input_schema": {            
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
]


class Agent:
    def __init__(self, model: str = "claude-sonnet-4-5"):
        self.client = Anthropic()
        self.model = model
        self.scratchpad: list = []
        self.recent_events: list = []
        self.recent_actions: list = []
        self.turn = 0
        self.last_thought = ""
        self.last_action = None

    def step(self, world: World) -> dict:
        """
        One agent step:
          - Build observation
          - Send to Claude
          - Parse the tool call
          - Apply action to world (returns action result)
          - Return a dict describing what happened
        """
        self.turn += 1
        observation = build_observation(
            world=world,
            scratchpad=self.scratchpad,
            recent_events=self.recent_events[-10:],
            turn=self.turn,
        )

        # Detect loops in two ways:
        # 1. Exact action repeated 3+ times
        # 2. Same target object touched 4+ times in last 6 actions (pick/drop thrash)
        nudge = ""
        recent_actions_str = [
            f"{a['verb']}({sorted(a['args'].items())})"
            for a in self.recent_actions[-4:]
        ]
        if recent_actions_str:
            most_recent = recent_actions_str[-1]
            if recent_actions_str.count(most_recent) >= 3:
                nudge = (
                    "\n\nNOTICE: You have just done the same action multiple times "
                    "in a row with no progress. STOP. Do something different."
                )
        
        # Wandering detector: many moves in a row without doing anything else
        if not nudge and len(self.recent_actions) >= 8:
            last_8 = self.recent_actions[-8:]
            if all(a["verb"] in ("move", "move_path") for a in last_8):
                nudge = (
                    "\n\nNOTICE: You have moved 8 times in a row without taking any other action. "
                    "You are wandering. STOP and check your INVENTORY and PUZZLE PROGRESS sections in the "
                    "observation above. Do not trust your scratchpad if it disagrees."
                )

        # Thrash detector: same object id touched 4+ times in last 6 actions
        if not nudge:
            recent_targets = []
            for a in self.recent_actions[-6:]:
                for v in a["args"].values():
                    if isinstance(v, str):
                        recent_targets.append(v)
            for target in set(recent_targets):
                if recent_targets.count(target) >= 4:
                    nudge = (
                        f"\n\nNOTICE: You have been interacting with '{target}' "
                        f"repeatedly. If it's correctly placed, LEAVE IT ALONE and "
                        f"move on to something else."
                    )
                    break
        full_observation = observation + nudge

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=[{"role": "user", "content": full_observation}],
        )

        # Extract thinking text and tool call
        thought_parts = []
        tool_call = None
        for block in response.content:
            if block.type == "text":
                thought_parts.append(block.text)
            elif block.type == "tool_use":
                tool_call = block
        thought = " ".join(thought_parts).strip()
        self.last_thought = thought

        if tool_call is None:
            # Claude responded with text only. Treat as a no-op + record.
            self.recent_events.append("(agent produced no action this turn)")
            return {
                "turn": self.turn,
                "observation": observation,
                "thought": thought,
                "action": None,
                "result": {"success": False, "message": "No action taken."},
            }

        verb = tool_call.name
        args = tool_call.input or {}
        self.last_action = {"verb": verb, "args": args}

        self.recent_actions.append(self.last_action)
        self.recent_actions = self.recent_actions[-20:]

        result = self._apply(world, verb, args)
        self.recent_events.append(result["message"])
        # Cap recent events log size in memory
        self.recent_events = self.recent_events[-50:]

        return {
            "turn": self.turn,
            "observation": observation,
            "thought": thought,
            "action": {"verb": verb, "args": args},
            "result": result,
        }

    def _apply(self, world: World, verb: str, args: dict) -> dict:
        """Translate an LLM tool call into a world action or scratchpad update."""
        if verb == "remember":
            text = args.get("text", "").strip()
            if text:
                self.scratchpad.append(text)
                return {"success": True, "message": f"Remembered: {text}"}
            return {"success": False, "message": "Empty remember() ignored."}

        if verb == "move":
            return world.move(args["direction"])
        if verb == "flip":
            return world.flip_lever(args["lever_id"])
        if verb == "read":
            return world.read(args["note_id"])
        if verb == "pick_up":
            return world.pick_up(args["box_id"])
        if verb == "drop":
            return world.drop(args["box_id"])
        if verb == "inspect":
            return world.inspect(args["box_id"])
        if verb == "move_path":
            directions = args.get("directions", [])
            if not directions:
                return {"success": False, "message": "Empty path."}
            if len(directions) > 8:
                directions = directions[:8]
            executed = []
            for i, d in enumerate(directions):
                result = world.move(d)
                if not result["success"]:
                    msg = (
                        f"Path executed {i} of {len(directions)} steps "
                        f"({', '.join(executed)}). Step {i+1} ({d}) failed: {result['message']}"
                    )
                    return {"success": False, "message": msg}
                executed.append(d)
            return {
                "success": True,
                "message": f"Walked the path: {', '.join(executed)}.",
            }
        
        return {"success": False, "message": f"Unknown action: {verb}"}
        