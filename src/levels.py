"""
Level definitions: a 3-room escape room.
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

    # ----- Room 1: binary levers, the safety lever, the box, notes -----
    lever_ids = [f"lever_{i}" for i in range(8)]
    for i, lid in enumerate(lever_ids):
        grid[18][i + 2].objects.append(Lever(id=lid))

    # The isolated safety lever — far from the others
    grid[16][12].objects.append(Lever(id="lever_safety"))

    grid[19][3].objects.append(Note(
        id="note_levers",
        text="To unlock door_1, set the levers 0-7 to encode 170. Lever 0 is the least significant bit.",
    ))

    grid[16][2].objects.append(Box(id="box_1", label="C"))

    # ----- Room 2A: plates + boxes + notes -----
    grid[10][3].terrain = Terrain.PRESSURE_PLATE
    grid[10][3].plate_color = "red"
    grid[10][7].terrain = Terrain.PRESSURE_PLATE
    grid[10][7].plate_color = "green"
    grid[10][11].terrain = Terrain.PRESSURE_PLATE
    grid[10][11].plate_color = "blue"

    grid[12][6].objects.append(Box(id="box_2", label="A"))
    grid[12][10].objects.append(Box(id="box_3", label="B"))

    grid[9][10].objects.append(Note(
        id="note_plates",
        text="Place each labeled box on its matching plate to unlock door_2. Removing a box re-locks the door.",
    ))
    grid[11][4].objects.append(Note(
        id="note_mapping",
        text="Box->Plate mapping: A goes on red, B goes on green, C goes on blue. Inspect a box to see its label.",
    ))

    # ----- Room 3: yellow plate + notes -----
    grid[3][7].terrain = Terrain.PRESSURE_PLATE
    grid[3][7].plate_color = "yellow"

    # Exit door at the very top
    grid[1][7].terrain = Terrain.DOOR_LOCKED
    grid[1][7].door_id = "door_exit"

    grid[5][3].objects.append(Note(
        id="note_safety",
        text=(
            "An extra lever waits in the first room, set apart from the others. "
            "Flipping it freezes the second door open, but only after you have read this. "
            "Without it, removing a box will re-lock the door behind you."
        ),
    ))

    grid[5][11].objects.append(Note(
        id="note_yellow",
        text="Place any box on the yellow plate to open the exit. WARNING: removing a box from its colored plate will re-lock door_2. Look around this room for another note about how to safely move boxes.",
    ))

    # ----- Build the World -----
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
            "door_exit": {
                "locked": True,
                "puzzle": "box_on_yellow",
                "position": (7, 1),
                "is_exit": True,
            },
        },
    )
    return world


build_level_1 = build_world