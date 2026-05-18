"""
Render the world to the terminal. ASCII for the spatial view.
"""
from src.world import World, Terrain, Lever, Note


def render_ascii(world: World) -> str:
    """Returns a string showing the grid. Used for both humans and the LLM."""
    lines = []
    for y in range(world.height):
        row_chars = []
        for x in range(world.width):
            cell = world.grid[y][x]
            if (x, y) == world.agent_pos:
                row_chars.append("@")
            elif cell.objects:
                # Show the first object's symbol
                obj = cell.objects[0]
                if isinstance(obj, Lever):
                    row_chars.append("|" if obj.is_up else "_")
                elif isinstance(obj, Note):
                    row_chars.append("?")
                else:
                    row_chars.append("o")
            else:
                row_chars.append(cell.terrain.value)
        lines.append("".join(row_chars))
    return "\n".join(lines)


def render_legend() -> str:
    return (
        "Legend: @ = you, # = wall, . = floor, D = locked door, "
        "/ = open door, E = exit, | = lever UP, _ = lever DOWN, ? = note"
    )