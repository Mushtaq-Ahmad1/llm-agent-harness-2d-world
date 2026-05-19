"""
Convert a World into a JSON-friendly dict the browser can render.
Also computes legal actions, which double as the agent's action menu.
"""
from src.world import World, Terrain, Lever, Note, Box


def _serialize_object(obj):
    if isinstance(obj, Lever):
        return {"type": "lever", "id": obj.id, "is_up": obj.is_up}
    if isinstance(obj, Note):
        return {"type": "note", "id": obj.id}
    if isinstance(obj, Box):
        return {"type": "box", "id": obj.id}
    return {"type": "unknown"}


def world_to_dict(world: World) -> dict:
    cells = []
    for y in range(world.height):
        row = []
        for x in range(world.width):
            cell = world.grid[y][x]
            row.append({
                "terrain": cell.terrain.name,
                "objects": [_serialize_object(o) for o in cell.objects],
                "door_id": cell.door_id,
                "plate_color": cell.plate_color,
            })
        cells.append(row)

    return {
        "width": world.width,
        "height": world.height,
        "cells": cells,
        "agent_pos": list(world.agent_pos),
        "inventory": [_serialize_object(o) for o in world.inventory],
        "won": world.won,
        "doors": {
            door_id: {"locked": info["locked"]}
            for door_id, info in world.doors.items()
        },
    }


def movement_actions(world: World) -> list:
    """All four move directions, each with a `legal` flag."""
    x, y = world.agent_pos
    out = []
    for direction, (dx, dy) in [
        ("north", (0, -1)),
        ("south", (0, 1)),
        ("east", (1, 0)),
        ("west", (-1, 0)),
    ]:
        target = world.cell_at(x + dx, y + dy)
        legal = True
        if target is None or target.terrain == Terrain.WALL:
            legal = False
        elif target.terrain == Terrain.DOOR_LOCKED:
            legal = False
        elif any(isinstance(obj, Box) for obj in target.objects):
            legal = False
        arrows = {"north": "↑", "south": "↓", "east": "→", "west": "←"}
        out.append({"verb": "move", "args": [direction], "label": f"{arrows[direction]} {direction.title()}", "legal": legal})
    return out


def interaction_actions(world: World) -> list:
    """All non-movement actions currently legal."""
    actions = []
    x, y = world.agent_pos

    seen_ids = set()
    for dx, dy in [(0, 0), (0, -1), (0, 1), (1, 0), (-1, 0)]:
        cell = world.cell_at(x + dx, y + dy)
        if cell is None:
            continue
        same_cell = (dx == 0 and dy == 0)
        for obj in cell.objects:
            if obj.id in seen_ids:
                continue
            seen_ids.add(obj.id)
            if isinstance(obj, Lever):
                if same_cell:
                    actions.append({"verb": "flip", "args": [obj.id], "label": f"Flip {obj.id}"})
            elif isinstance(obj, Note):
                actions.append({"verb": "read", "args": [obj.id], "label": f"Read {obj.id}"})
            elif isinstance(obj, Box):
                actions.append({"verb": "inspect", "args": [obj.id], "label": f"Inspect {obj.id}"})
                actions.append({"verb": "pick_up", "args": [obj.id], "label": f"Pick up {obj.id}"})

    for obj in world.inventory:
        if isinstance(obj, Box):
            actions.append({"verb": "inspect", "args": [obj.id], "label": f"Inspect {obj.id} (held)"})
            actions.append({"verb": "drop", "args": [obj.id], "label": f"Drop {obj.id}"})

    return actions


def legal_actions(world: World) -> list:
    """Combined list of currently-legal actions. Used by the LLM agent later."""
    return [a for a in movement_actions(world) if a["legal"]] + interaction_actions(world)