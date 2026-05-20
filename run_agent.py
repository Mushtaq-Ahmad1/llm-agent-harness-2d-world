"""
Headless agent runner. Prints what the agent does each turn.
Use this to test the agent loop before adding the GUI.
"""
from src.levels import build_world
from src.agent import Agent

MAX_STEPS = 100


def main():
    world = build_world()
    agent = Agent(model="claude-haiku-4-5")

    print(f"Starting agent. Initial position: {world.agent_pos}\n")

    for _ in range(MAX_STEPS):
        info = agent.step(world)

        print(f"--- Turn {info['turn']} ---")
        if info["thought"]:
            # Trim multi-line thoughts for terminal readability
            short = info["thought"][:400]
            print(f"THOUGHT: {short}{'…' if len(info['thought']) > 400 else ''}")
        if info["action"]:
            verb = info["action"]["verb"]
            args = info["action"]["args"]
            print(f"ACTION: {verb}({args})")
        print(f"RESULT: {info['result']['message']}")
        print()

        if world.won:
            print(f"WON in {info['turn']} turns.")
            return

    print(f"Did not win in {MAX_STEPS} steps. Final position: {world.agent_pos}")


if __name__ == "__main__":
    main()