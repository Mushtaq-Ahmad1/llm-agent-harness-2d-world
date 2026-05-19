"""
Convert a World into a JSON-friendly dict the browser can render.
This is also a useful reference for what the human/UI needs to know.
"""
from src.world import World, Terrain, Lever, Note


def world_to_dict(world: World) -> dict:
    cells = []
    for y in range(world.height):
        row = []
        for x in range(world.width):
            cell = world.grid[y][x]
            cell_data = {
                "terrain": cell.terrain.name,
                "objects": [],
                "door_id": cell.door_id,
            }
            for obj in cell.objects:
                if isinstance(obj, Lever):
                    cell_data["objects"].append({
                        "type": "lever",
                        "id": obj.id,
                        "is_up": obj.is_up,
                    })
                elif isinstance(obj, Note):
                    cell_data["objects"].append({
                        "type": "note",
                        "id": obj.id,
                    })
            row.append(cell_data)
        cells.append(row)

    return {
        "width": world.width,
        "height": world.height,
        "cells": cells,
        "agent_pos": list(world.agent_pos),
        "inventory": world.inventory,
        "won": world.won,
        "doors": {
            door_id: {"locked": info["locked"]}
            for door_id, info in world.doors.items()
        },
    }


def legal_actions(world: World) -> list:
    """
    Compute what actions are currently legal from the agent's position.
    Returns a list of action dicts the UI can render as buttons.
    """
    actions = []
    x, y = world.agent_pos

    # Movement
    for direction, (dx, dy) in [
        ("north", (0, -1)),
        ("south", (0, 1)),
        ("east", (1, 0)),
        ("west", (-1, 0)),
    ]:
        target = world.cell_at(x + dx, y + dy)
        if target is not None and target.terrain != Terrain.WALL:
            actions.append({"verb": "move", "args": [direction], "label": f"Move {direction}"})

    # Interactions with nearby objects
    for dx, dy in [(0, 0), (0, -1), (0, 1), (1, 0), (-1, 0)]:
        cell = world.cell_at(x + dx, y + dy)
        if cell is None:
            continue
        for obj in cell.objects:
            if isinstance(obj, Lever):
                actions.append({"verb": "flip", "args": [obj.id], "label": f"Flip {obj.id}"})
            elif isinstance(obj, Note):
                actions.append({"verb": "read", "args": [obj.id], "label": f"Read {obj.id}"})

    # Try doors (any door we know about)
    for door_id, info in world.doors.items():
        if info["locked"]:
            actions.append({"verb": "open", "args": [door_id], "label": f"Try {door_id}"})

    return actions