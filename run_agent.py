"""
Headless agent runner. Prints what the agent does each turn.
Use this to test the agent loop before adding the GUI.
"""
import sys
import io
# Force stdout/stderr to UTF-8 so arrow characters and emojis in agent
# output don't crash on Windows (which defaults to cp1252).
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
from datetime import datetime
from src.levels import build_world
from src.agent import Agent

MAX_STEPS = 100

import sys
from datetime import datetime

def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "claude-sonnet-4-5"

    print(f"{'=' * 60}")
    print(f"AGENT RUN — model: {model}")
    print(f"Started: {datetime.now().isoformat(timespec='seconds')}")
    print(f"Max steps: {MAX_STEPS}")
    print(f"{'=' * 60}\n")

    world = build_world()
    agent = Agent(model=model)

    print(f"Initial position: {world.agent_pos}\n")

    for _ in range(MAX_STEPS):
        info = agent.step(world)

        print(f"--- Turn {info['turn']} ---")
        if info["thought"]:
            short = info["thought"][:600]
            print(f"THOUGHT: {short}{'…' if len(info['thought']) > 600 else ''}")
        if info["action"]:
            verb = info["action"]["verb"]
            args = info["action"]["args"]
            print(f"ACTION: {verb}({args})")
        print(f"RESULT: {info['result']['message']}")
        print()

        if world.won:
            print(f"{'=' * 60}")
            print(f"WON in {info['turn']} turns.")
            print(f"Final scratchpad ({len(agent.scratchpad)} entries):")
            for note in agent.scratchpad:
                print(f"  - {note}")
            print(f"{'=' * 60}")
            return

    print(f"{'=' * 60}")
    print(f"DID NOT WIN in {MAX_STEPS} steps.")
    print(f"Final position: {world.agent_pos}")
    print(f"Final inventory: {[o.id for o in world.inventory]}")
    print(f"Final scratchpad:")
    for note in agent.scratchpad:
        print(f"  - {note}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()