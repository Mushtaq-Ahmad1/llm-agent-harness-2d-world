"""
Build the text observation we send to the LLM each turn.

Design notes:
- Structured text + small ASCII view. The ASCII view is local (5x5) to keep
  the LLM out of trouble counting cells across a big grid.
- Coordinates are first-class: spatial reasoning from pure ASCII is hard, but
  reasoning over named coordinates is easy.
- We list ONLY currently-legal actions with their exact arguments. The agent
  never has to guess what's allowed.
"""

from src.world import World, Terrain, Lever, Note, Box
from src.serialize import legal_actions
from collections import deque


VIEW_RADIUS = 3  # 7x7 view


def build_observation(
    world: World,
    scratchpad: list,
    recent_events: list,
    turn: int,
) -> str:
    parts = []
    parts.append(f"=== TURN {turn} ===\n")
    parts.append("GOAL: Escape the room by stepping onto the EXIT tile (terrain 'E').\n")

    x, y = world.agent_pos
    reachable = _reachable_cells(world)

    parts.append(f"YOUR INVENTORY: {_describe_inventory(world)}\n")
    parts.append(f"YOUR POSITION: ({x}, {y})  (x increases east, y increases south)")
    parts.append(f"REACHABLE CELLS FROM HERE: {len(reachable)} (objects outside this are blocked by walls or locked doors)")
    
    parts.append(f"LOCAL VIEW ({VIEW_RADIUS*2+1}x{VIEW_RADIUS*2+1} around you, @ = you):")
    parts.append(_local_ascii(world))
    parts.append(
        "  Legend: . floor  # wall  D locked-door  / open-door  E exit  "
        "P plate  l lever  n note  b box  @ you"
    )
    parts.append("")

    parts.append("VISIBLE OBJECTS NEAR YOU (within 5 cells):")
    nearby_lines = _nearby_objects(world, reachable)
    if nearby_lines:
        parts.extend(f"  - {line}" for line in nearby_lines)
    else:
        parts.append("  (nothing nearby)")
    parts.append("")

    # Surface boxes as a dedicated priority section
    boxes_nearby = []
    for dy in range(-5, 6):
        for dx in range(-5, 6):
            cell = world.cell_at(x + dx, y + dy)
            if cell is None:
                continue
            for obj in cell.objects:
                if isinstance(obj, Box):
                    placed = _is_box_correctly_placed(world, cell, obj)
                    # Only hide boxes that are "locked into place" by an active puzzle.
                    # If safety lever is used, those plates aren't gating anything anymore.
                    if placed and not world.safety_used:
                        continue
                    boxes_nearby.append((obj.id, x + dx, y + dy))
    if boxes_nearby:
        parts.append("BOXES IN VIEW (priority — pick them up before leaving the area):")
        for box_id, bx, by in boxes_nearby:
            blocked = "" if (bx, by) in reachable else "  [BLOCKED by locked door or wall]"
            parts.append(f"  - {box_id} at ({bx}, {by}){blocked}")
        parts.append("")

    parts.append("PUZZLE PROGRESS (ground truth from the world — trust this):")
    progress = _puzzle_progress(world)
    if progress:
        for line in progress:
            parts.append(f"  - {line}")
    else:
        parts.append("  (no progress yet)")
    parts.append("")

    parts.append("DOOR STATUS:")
    for door_id, info in world.doors.items():
        state = "LOCKED" if info["locked"] else "OPEN"
        parts.append(f"  - {door_id} at {info['position']}: {state}")
    parts.append("")

    parts.append("YOUR NOTES (scratchpad):")
    if scratchpad:
        # Show last 8 entries to keep scratchpad fresh
        recent_scratchpad = scratchpad[-8:]
        if len(scratchpad) > 8:
            parts.append(f"  ({len(scratchpad) - 8} older notes omitted)")
        for note in recent_scratchpad:
            parts.append(f"  - {note}")
    else:
        parts.append("  (empty — use remember() to write things down)")

    parts.append(f"RECENT EVENTS (last {len(recent_events)}):")
    if recent_events:
        counts = {}
        for ev in recent_events:
            counts[ev] = counts.get(ev, 0) + 1
        for ev in recent_events:
            tag = "  ← YOU HAVE DONE THIS REPEATEDLY. STOP." if counts[ev] >= 3 else ""
            parts.append(f"  - {ev}{tag}")
    else:
        parts.append("  (none yet)")
    parts.append("")

    parts.append("AVAILABLE ACTIONS THIS TURN:")
    for action in legal_actions(world):
        verb = action["verb"]
        args = action["args"]
        if args:
            parts.append(f"  - {verb}({', '.join(args)})")
        else:
            parts.append(f"  - {verb}()")
    parts.append("")
    parts.append("Reminder: if you've figured out a fact (a code, a mapping, where an object is), `remember` it FIRST before doing anything else.")
    parts.append("Have you read every note in your area? Inspected every box? Picked up every box you can? If not, do that first.")
    parts.append("Think briefly, then call ONE action tool.")

    return "\n".join(parts)

def _is_box_correctly_placed(world: World, cell, box) -> bool:
    """True if this box is sitting on the plate it's supposed to go on."""
    if cell.terrain != Terrain.PRESSURE_PLATE:
        return False
    for door_info in world.doors.values():
        if door_info.get("puzzle") != "pressure_plates":
            continue
        required_label = door_info["required"].get(cell.plate_color)
        if required_label is not None and box.label == required_label:
            return True
    return False

def _describe_inventory(world: World) -> str:
    if not world.inventory:
        return "(empty)"
    descriptions = []
    for obj in world.inventory:
        if isinstance(obj, Box):
            label = f", label: {obj.label}" if obj.label_revealed else ", label unknown (inspect to see)"
            descriptions.append(f"{obj.id}{label}")
        else:
            descriptions.append(obj.id)
    return ", ".join(descriptions)

def _local_ascii(world: World) -> str:
    ax, ay = world.agent_pos
    lines = []
    for dy in range(-VIEW_RADIUS, VIEW_RADIUS + 1):
        row = []
        for dx in range(-VIEW_RADIUS, VIEW_RADIUS + 1):
            x, y = ax + dx, ay + dy
            cell = world.cell_at(x, y)
            if cell is None:
                row.append("#")  # off-map treated as wall
                continue
            if (dx, dy) == (0, 0):
                row.append("@")
                continue
            # Object on cell takes priority for display
            if cell.objects:
                obj = cell.objects[0]
                if isinstance(obj, Lever):
                    row.append("l")
                elif isinstance(obj, Note):
                    row.append("n")
                elif isinstance(obj, Box):
                    row.append("b")
                else:
                    row.append("?")
                continue
            symbol = {
                Terrain.FLOOR: ".",
                Terrain.WALL: "#",
                Terrain.DOOR_LOCKED: "D",
                Terrain.DOOR_OPEN: "/",
                Terrain.EXIT: "E",
                Terrain.PRESSURE_PLATE: "P",
            }.get(cell.terrain, "?")
            row.append(symbol)
        lines.append("  " + " ".join(row))
    return "\n".join(lines)

def _nearby_objects(world: World, reachable: set, radius: int = 5) -> list:
    ax, ay = world.agent_pos
    found = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            x, y = ax + dx, ay + dy
            cell = world.cell_at(x, y)
            if cell is None:
                continue
            # The cell terrain itself
            reach_tag = "" if (x, y) in reachable else "  [BLOCKED — cannot reach from here]"
            if cell.terrain == Terrain.PRESSURE_PLATE:
                contents = [o for o in cell.objects if isinstance(o, Box)]
                if contents:
                    box = contents[0]
                    label = f"label {box.label}" if box.label_revealed else "label unknown"
                    correct = _is_box_correctly_placed(world, cell, box)
                    if correct and not world.safety_used:
                        status = " [CORRECT — do not touch; moving it re-locks the door]"
                    elif correct and world.safety_used:
                        status = " [CORRECT — safe to move if needed]"
                    else:
                        status = " [WRONG box]"
                    found.append(f"{cell.plate_color} plate at ({x},{y}), holds {box.id} ({label}){status}{reach_tag}")
                else:
                    found.append(f"{cell.plate_color} plate at ({x},{y}), empty{reach_tag}")
            elif cell.terrain == Terrain.DOOR_LOCKED:
                found.append(f"locked door '{cell.door_id}' at ({x},{y})")
            elif cell.terrain == Terrain.DOOR_OPEN:
                found.append(f"open door '{cell.door_id}' at ({x},{y})")
            elif cell.terrain == Terrain.EXIT:
                found.append(f"EXIT tile at ({x},{y})")
            # Objects (skip boxes already mentioned via their plate)
            for obj in cell.objects:
                if cell.terrain == Terrain.PRESSURE_PLATE and isinstance(obj, Box):
                    continue
                if isinstance(obj, Lever):
                    state = "UP" if obj.is_up else "DOWN"
                    found.append(f"lever '{obj.id}' at ({x},{y}), currently {state}")
                elif isinstance(obj, Note):
                    found.append(f"note '{obj.id}' at ({x},{y}) — read it to learn more")
                elif isinstance(obj, Box):
                    label = f"label {obj.label}" if obj.label_revealed else "label unknown (inspect to see)"
                    found.append(f"box '{obj.id}' at ({x},{y}), {label}")
    return found

def _puzzle_progress(world: World) -> list:
    """Concise summary of solved/unsolved puzzle elements. Helps the agent
    trust that an action stuck without re-checking."""
    lines = []
    for door_id, info in world.doors.items():
        if info["puzzle"] == "pressure_plates":
            required = info["required"]
            for color, expected_label in required.items():
                plate_cell = world._find_plate_cell(color)
                if plate_cell is None:
                    continue
                box = next((o for o in plate_cell.objects if isinstance(o, Box)), None)
                if box is None:
                    lines.append(f"{color} plate: EMPTY (needs box labeled {expected_label})")
                elif box.label == expected_label:
                    lines.append(f"{color} plate: CORRECT — has {box.id} (label {box.label})")
                else:
                    lines.append(f"{color} plate: WRONG box — has {box.id} (label {box.label}), needs {expected_label}")
        elif info["puzzle"] == "binary_levers":
            value = 0
            for i, lid in enumerate(info["lever_ids"]):
                lever = world._find_lever(lid)
                if lever and lever.is_up:
                    value += 2 ** i
            target = info["target"]
            status = "CORRECT" if value == target else f"current value {value}, needs {target}"
            lines.append(f"binary levers: {status}")
    return lines

def _reachable_cells(world: World) -> set:
    """BFS from agent position. Returns set of (x, y) reachable without
    crossing walls or locked doors. Used to flag objects the agent
    can SEE but cannot actually walk to."""
    start = world.agent_pos
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in [(0, -1), (0, 1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if (nx, ny) in seen:
                continue
            cell = world.cell_at(nx, ny)
            if cell is None:
                continue
            if cell.terrain == Terrain.WALL:
                continue
            if cell.terrain == Terrain.DOOR_LOCKED:
                continue
            seen.add((nx, ny))
            q.append((nx, ny))
    return seen