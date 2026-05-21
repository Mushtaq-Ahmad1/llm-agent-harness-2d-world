"""
World: the 2D grid environment.

Design notes:
- Grid is row-major: grid[y][x]. y=0 is the top row.
- All actions return a dict with `success` (bool) and `message` (str).
  The message is what the agent will read as feedback.
- Puzzles register themselves with the world and gate doors via puzzle_state.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Terrain(Enum):
    FLOOR = "."
    WALL = "#"
    DOOR_LOCKED = "D"
    DOOR_OPEN = "/"
    EXIT = "E"
    PRESSURE_PLATE = "P"


@dataclass
class Lever:
    id: str
    is_up: bool = False

    def flip(self):
        self.is_up = not self.is_up

@dataclass
class Note:
    id: str
    text: str

@dataclass
class Box:
    id: str
    label: str  # the secret label (A, B, C) — revealed by inspect
    label_revealed: bool = False

@dataclass
class Cell:
    terrain: Terrain = Terrain.FLOOR
    objects: list = field(default_factory=list)
    door_id: Optional[str] = None  # if terrain is DOOR, which door
    plate_color: Optional[str] = None  # for PRESSURE_PLATE cells

    @property
    def is_passable(self) -> bool:
        if self.terrain == Terrain.WALL:
            return False
        if self.terrain == Terrain.DOOR_LOCKED:
            return False
        return True

@dataclass
class World:
    width: int
    height: int
    grid: list = field(default_factory=list)
    agent_pos: tuple = (0, 0)
    inventory: list = field(default_factory=list)
    puzzle_state: dict = field(default_factory=dict)
    doors: dict = field(default_factory=dict)  # door_id -> {"locked": bool, "puzzle": str}
    won: bool = False
    safety_armed: bool = False
    safety_used: bool = False

    def cell_at(self, x: int, y: int) -> Optional[Cell]:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[y][x]
        return None

    # ---- Actions ----
    # All actions return {"success": bool, "message": str}

    def move(self, direction: str) -> dict:
        dx, dy = {
            "north": (0, -1),
            "south": (0, 1),
            "east": (1, 0),
            "west": (-1, 0),
        }.get(direction, (0, 0))

        if (dx, dy) == (0, 0):
            return {"success": False, "message": f"Unknown direction: {direction}."}

        x, y = self.agent_pos
        nx, ny = x + dx, y + dy
        target = self.cell_at(nx, ny)

        if target is None:
            return {"success": False, "message": "You can't move off the map."}
        # Can't walk through walls
        if target.terrain == Terrain.WALL:
            # Helpful hint: are there open doors or floor cells just to the sides?
            hints = []
            for label, (dx2, dy2) in [
                ("east", (1, 0)),
                ("west", (-1, 0)),
            ]:
                near = self.cell_at(x + dx2, y + dy2)
                if near and near.terrain == Terrain.DOOR_OPEN:
                    hints.append(f"there's an open door one cell {label}")
                elif near and near.terrain == Terrain.DOOR_LOCKED:
                    hints.append(f"there's a locked door one cell {label}")
            extra = f" ({'; '.join(hints)})" if hints else ""
            return {"success": False, "message": f"A wall blocks your path.{extra}"}
        # Can't walk through locked doors
        if target.terrain == Terrain.DOOR_LOCKED:         
            return {"success": False, "message": f"The door to the {direction} is locked."}
        # Can't walk onto a cell occupied by a box
        if any(isinstance(obj, Box) for obj in target.objects):
            return {"success": False, "message": f"A box is in the way to the {direction}."}

        self.agent_pos = (nx, ny)

        if target.terrain == Terrain.EXIT:
            self.won = True
            return {"success": True, "message": "You stepped onto the exit. You escaped!"}

        return {"success": True, "message": f"You moved {direction}."}

    def flip_lever(self, lever_id: str) -> dict:
        x, y = self.agent_pos
        cell = self.cell_at(x, y)
        if cell is None:
            return {"success": False, "message": "Nothing here."}
        for obj in cell.objects:
            if isinstance(obj, Lever) and obj.id == lever_id:
                # Safety lever has special behaviour
                if lever_id == "lever_safety":
                    if not self.safety_armed:
                        return {"success": False, "message": "The lever doesn't budge. It seems inert for now."}
                    if self.safety_used:
                        return {"success": False, "message": "The lever is locked in place — it has already been used."}
                    obj.flip()
                    self.safety_used = True
                    door_msgs = self._check_doors()
                    msg = "You flip the safety lever. You hear a deep click somewhere far above."
                    if door_msgs:
                        msg += " " + " ".join(door_msgs)
                    return {"success": True, "message": msg}
                # Normal lever
                obj.flip()
                state = "UP" if obj.is_up else "DOWN"
                result = {"success": True, "message": f"You flipped {lever_id} to {state}."}
                door_msgs = self._check_doors()
                if door_msgs:
                    result["message"] += " " + " ".join(door_msgs)
                return result
        return {"success": False, "message": f"No lever named {lever_id} on this cell."}

    def read(self, note_id: str) -> dict:
        x, y = self.agent_pos
        cell = self.cell_at(x, y)
        candidates = [cell] + [self.cell_at(x + dx, y + dy) for dx, dy in [(0, -1), (0, 1), (1, 0), (-1, 0)]]
        for c in candidates:
            if c is None:
                continue
            for obj in c.objects:
                if isinstance(obj, Note) and obj.id == note_id:
                    extra = ""
                    if obj.id == "note_safety" and not self.safety_armed:
                        self.safety_armed = True
                        extra = " (You sense the extra lever in the first room now feels active.)"
                    return {"success": True, "message": f'It reads: "{obj.text}"{extra}'}
        return {"success": False, "message": f"Nothing to read named {note_id} nearby."}

    def _check_doors(self) -> list:
        """
        Check every door against its puzzle. Transitions emit messages:
          - locked + solved        -> unlock
          - unlocked + not solved  -> re-lock
        Special case: once safety lever has been used, door_2 stays unlocked.
        """
        messages = []
        door_labels = {
            "door_1": "the first door",
            "door_2": "the second door",
            "door_exit": "the exit",
        }
        for door_id, info in self.doors.items():
            solved = self._puzzle_solved(door_id, info)

            # Safety lever freezes door_2 open permanently
            if door_id == "door_2" and self.safety_used:
                solved = True

            label = door_labels.get(door_id, door_id)
            dx, dy = info["position"]

            if info["locked"] and solved:
                info["locked"] = False
                if info.get("is_exit"):
                    self.grid[dy][dx].terrain = Terrain.EXIT
                else:
                    self.grid[dy][dx].terrain = Terrain.DOOR_OPEN
                messages.append(f"You have opened {label}.")

            elif not info["locked"] and not solved:
                info["locked"] = True
                self.grid[dy][dx].terrain = Terrain.DOOR_LOCKED
                messages.append(f"{label.capitalize()} re-locked behind you!")

        return messages

    def _puzzle_solved(self, door_id: str, info: dict) -> bool:
        puzzle_name = info["puzzle"]
        if puzzle_name == "binary_levers":
            target = info["target"]
            value = 0
            for i, lid in enumerate(info["lever_ids"]):
                lever = self._find_lever(lid)
                if lever and lever.is_up:
                    value += 2 ** i
            return value == target
        if puzzle_name == "pressure_plates":
            required = info["required"]
            for color, expected_label in required.items():
                plate_cell = self._find_plate_cell(color)
                if plate_cell is None:
                    return False
                box = next((o for o in plate_cell.objects if isinstance(o, Box)), None)
                if box is None or box.label != expected_label:
                    return False
            return True
        if puzzle_name == "box_on_yellow":
            plate_cell = self._find_plate_cell("yellow")
            if plate_cell is None:
                return False
            return any(isinstance(o, Box) for o in plate_cell.objects)
        return False
    
    def _find_plate_cell(self, color: str) -> Optional[Cell]:
        for row in self.grid:
            for cell in row:
                if cell.terrain == Terrain.PRESSURE_PLATE and cell.plate_color == color:
                    return cell
        return None

    def _find_lever(self, lever_id: str) -> Optional[Lever]:
        for row in self.grid:
            for cell in row:
                for obj in cell.objects:
                    if isinstance(obj, Lever) and obj.id == lever_id:
                        return obj
        return None
    
    def pick_up(self, obj_id: str) -> dict:
        x, y = self.agent_pos
        candidates = [self.cell_at(x, y)] + [
            self.cell_at(x + dx, y + dy) for dx, dy in [(0, -1), (0, 1), (1, 0), (-1, 0)]
        ]
        for c in candidates:
            if c is None:
                continue
            for obj in c.objects:
                if isinstance(obj, Box) and obj.id == obj_id:
                    c.objects.remove(obj)
                    self.inventory.append(obj)
                    result = {"success": True, "message": f"You picked up {obj_id}."}
                    door_msgs = self._check_doors()
                    if door_msgs:
                        result["message"] += " " + " ".join(door_msgs)
                    return result
        return {"success": False, "message": f"Nothing to pick up named {obj_id} nearby."}

    def drop(self, obj_id: str) -> dict:
        # Find the box in inventory
        obj = next((o for o in self.inventory if isinstance(o, Box) and o.id == obj_id), None)
        if obj is None:
            return {"success": False, "message": f"You aren't carrying {obj_id}."}

        x, y = self.agent_pos
        cell = self.cell_at(x, y)
        # Don't allow stacking boxes
        if any(isinstance(o, Box) for o in cell.objects):
            return {"success": False, "message": "There's already a box here."}

        self.inventory.remove(obj)
        cell.objects.append(obj)

        result = {"success": True, "message": f"You placed {obj_id} on the floor."}
        door_msgs = self._check_doors()
        if door_msgs:
            result["message"] += " " + " ".join(door_msgs)
        return result

    def inspect(self, obj_id: str) -> dict:
        # Check inventory
        for obj in self.inventory:
            if isinstance(obj, Box) and obj.id == obj_id:
                obj.label_revealed = True
                return {"success": True, "message": f"{obj_id} is labeled '{obj.label}'."}
        # Check current and adjacent cells
        x, y = self.agent_pos
        candidates = [self.cell_at(x, y)] + [
            self.cell_at(x + dx, y + dy) for dx, dy in [(0, -1), (0, 1), (1, 0), (-1, 0)]
        ]
        for c in candidates:
            if c is None:
                continue
            for obj in c.objects:
                if isinstance(obj, Box) and obj.id == obj_id:
                    obj.label_revealed = True
                    return {"success": True, "message": f"{obj_id} is labeled '{obj.label}'."}
        return {"success": False, "message": f"Nothing to inspect named {obj_id} nearby."}