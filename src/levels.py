"""
Level definitions: a 3-room escape room.

Room 1 (Level 1):  Binary-lever puzzle. Also contains box_1, which the agent
                   must carry forward to solve Room 2.
Room 2 (Level 2A): Pressure-plate puzzle. Three colored plates. Two boxes
                   here, one already brought from Room 1.
Room 3 (Level 2B): The exit.
"""
from src.world import World, Cell, Terrain, Lever, Note, Box


def build_world() -> World:
    width, height = 14, 22
    grid = [[Cell(terrain=Terrain.FLOOR) for _ in range(width)] for _ in range(height)]

    # ----- Outer walls -----
    for x in range(width):
        grid[0][x].terrain = Terrain.WALL
        grid[height - 1][x].terrain = Terrain.WALL
    for y in range(height):
        grid[y][0].terrain = Terrain.WALL
        grid[y][width - 1].terrain = Terrain.WALL

    # ----- Internal walls -----
    for x in range(width):
        grid[14][x].terrain = Terrain.WALL
        grid[7][x].terrain = Terrain.WALL

    # ----- Doors -----
    grid[14][7].terrain = Terrain.DOOR_LOCKED
    grid[14][7].door_id = "door_1"

    grid[7][7].terrain = Terrain.DOOR_LOCKED
    grid[7][7].door_id = "door_2"

    # ----- Room 1: binary levers + a box -----
    lever_ids = [f"lever_{i}" for i in range(8)]
    for i, lid in enumerate(lever_ids):
        grid[18][i + 2].objects.append(Lever(id=lid))

    grid[16][12].objects.append(Note(
        id="note_levers",
        text="To unlock door_1, set the levers to encode 170. Lever 0 is the least significant bit.",
    ))

    # The third box, hidden in Room 1. Agent must remember to take it.
    grid[16][2].objects.append(Box(id="box_1", label="C"))

    # ----- Room 2A: pressure plates + boxes + mapping note -----
    grid[10][3].terrain = Terrain.PRESSURE_PLATE
    grid[10][3].plate_color = "red"
    grid[10][7].terrain = Terrain.PRESSURE_PLATE
    grid[10][7].plate_color = "green"
    grid[10][11].terrain = Terrain.PRESSURE_PLATE
    grid[10][11].plate_color = "blue"

    grid[12][6].objects.append(Box(id="box_2", label="A"))
    grid[12][10].objects.append(Box(id="box_3", label="B"))

    grid[9][12].objects.append(Note(
        id="note_plates",
        text="Place each labeled box on its matching plate to unlock door_2.",
    ))

    grid[11][1].objects.append(Note(
        id="note_mapping",
        text="Box→Plate mapping: A goes on red, B goes on green, C goes on blue. Inspect a box to see its label.",
    ))

    # ----- Room 2B: exit -----
    grid[3][7].terrain = Terrain.EXIT
    grid[4][11].objects.append(Note(
        id="note_exit",
        text="You made it. Step onto the exit tile to escape.",
    ))

    world = World(
        width=width,
        height=height,
        grid=grid,
        agent_pos=(1, 19),
        doors={
            "door_1": {
                "locked": True,
                "puzzle": "binary_levers",
                "target": 170,
                "lever_ids": lever_ids,
                "position": (7, 14),
            },
            "door_2": {
                "locked": True,
                "puzzle": "pressure_plates",
                "required": {"red": "A", "green": "B", "blue": "C"},
                "position": (7, 7),
            },
        },
    )
    return world


build_level_1 = build_world