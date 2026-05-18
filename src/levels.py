"""
Level definitions. Start tiny, expand later.
"""
from src.world import World, Cell, Terrain, Lever, Note


def build_level_1() -> World:
    """
    Single room, 10 wide x 8 tall.
    Agent starts at (1, 6), exit is behind a binary-lever door at (5, 0).
    8 levers along the south wall. Note on east wall says 'code: 170'.
    170 in binary = 10101010, so levers 1,3,5,7 should be UP (0-indexed from the left).
    """
    width, height = 10, 8
    grid = [[Cell(terrain=Terrain.FLOOR) for _ in range(width)] for _ in range(height)]

    # Outer walls
    for x in range(width):
        grid[0][x].terrain = Terrain.WALL
        grid[height - 1][x].terrain = Terrain.WALL
    for y in range(height):
        grid[y][0].terrain = Terrain.WALL
        grid[y][width - 1].terrain = Terrain.WALL

    # The locked door at the top
    door_x, door_y = 5, 0
    grid[door_y][door_x].terrain = Terrain.DOOR_LOCKED
    grid[door_y][door_x].door_id = "north_door"

    # The exit just beyond would be off-map, so put exit IN the door cell
    # Simpler: when door opens, walking through it puts you on exit
    # Even simpler: place exit one row "above" by extending the map
    # Let's just say walking through the door = win
    # We do that by placing EXIT on the door cell after unlock... or just check won when stepping on opened door

    # Binary levers along row 5, columns 1-8
    lever_ids = [f"lever_{i}" for i in range(8)]
    for i, lid in enumerate(lever_ids):
        grid[5][i + 1].objects.append(Lever(id=lid))

    # Note on east wall
    grid[3][8].objects.append(Note(id="note_1", text="To unlock the door, set the levers to encode 170. Lever 0 is the least significant bit."))

    world = World(
        width=width,
        height=height,
        grid=grid,
        agent_pos=(1, 6),
        doors={
            "north_door": {
                "locked": True,
                "puzzle": "binary_levers",
                "target": 170,
                "lever_ids": lever_ids,
                "position": (door_x, door_y),
            }
        },
    )
    # Make stepping onto an opened door = winning, by also marking that cell EXIT once unlocked
    # We'll handle that in try_open_door — set it to EXIT instead of DOOR_OPEN for the final door
    # For simplicity in level 1, the door IS the exit:
    world.doors["north_door"]["is_exit"] = True
    return world