"""
Manual control loop. Lets a human play the game to test world mechanics.
The LLM agent loop will replace this later.
"""
from src.levels import build_level_1
from src.render import render_ascii, render_legend


def main():
    world = build_level_1()
    print(render_legend())
    print()

    while not world.won:
        print(render_ascii(world))
        print(f"Position: {world.agent_pos}  Inventory: {world.inventory}")
        cmd = input("> ").strip().lower()

        if not cmd:
            continue
        if cmd in ("quit", "exit", "q"):
            print("Goodbye.")
            return

        parts = cmd.split()
        verb = parts[0]
        args = parts[1:]

        if verb == "move" and args:
            result = world.move(args[0])
        elif verb in ("north", "south", "east", "west"):
            result = world.move(verb)
        elif verb == "flip" and args:
            result = world.flip_lever(args[0])
        elif verb == "read" and args:
            result = world.read(args[0])
        elif verb == "open" and args:
            result = world.try_open_door(args[0])
        else:
            result = {"success": False, "message": f"Unknown command: {cmd}"}

        print(result["message"])
        print()

    print("YOU WIN!")


if __name__ == "__main__":
    main()