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
class Cell:
    terrain: Terrain = Terrain.FLOOR
    objects: list = field(default_factory=list)
    door_id: Optional[str] = None  # if terrain is DOOR, which door

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
        if target.terrain == Terrain.WALL:
            return {"success": False, "message": "A wall blocks your path."}
        if target.terrain == Terrain.DOOR_LOCKED:
            return {"success": False, "message": f"The door to the {direction} is locked."}

        self.agent_pos = (nx, ny)

        if target.terrain == Terrain.EXIT:
            self.won = True
            return {"success": True, "message": "You stepped onto the exit. You escaped!"}

        return {"success": True, "message": f"You moved {direction}."}

    def flip_lever(self, lever_id: str) -> dict:
        x, y = self.agent_pos
        cell = self.cell_at(x, y)
        # Allow flipping levers in the current cell OR adjacent cells
        candidates = [cell] + [self.cell_at(x + dx, y + dy) for dx, dy in [(0, -1), (0, 1), (1, 0), (-1, 0)]]
        for c in candidates:
            if c is None:
                continue
            for obj in c.objects:
                if isinstance(obj, Lever) and obj.id == lever_id:
                    obj.flip()
                    state = "UP" if obj.is_up else "DOWN"
                    return {"success": True, "message": f"You flipped {lever_id} to {state}."}
        return {"success": False, "message": f"No lever named {lever_id} nearby."}

    def read(self, note_id: str) -> dict:
        x, y = self.agent_pos
        cell = self.cell_at(x, y)
        candidates = [cell] + [self.cell_at(x + dx, y + dy) for dx, dy in [(0, -1), (0, 1), (1, 0), (-1, 0)]]
        for c in candidates:
            if c is None:
                continue
            for obj in c.objects:
                if isinstance(obj, Note) and obj.id == note_id:
                    return {"success": True, "message": f'The note reads: "{obj.text}"'}
        return {"success": False, "message": f"No note named {note_id} nearby."}

    def try_open_door(self, door_id: str) -> dict:
        if door_id not in self.doors:
            return {"success": False, "message": f"No door named {door_id}."}
        info = self.doors[door_id]
        if not info["locked"]:
            return {"success": False, "message": f"{door_id} is already open."}

        # Check puzzle
        puzzle_name = info["puzzle"]
        if puzzle_name == "binary_levers":
            # The 8 levers should encode the target number
            target = info["target"]
            lever_ids = info["lever_ids"]
            value = 0
            for i, lid in enumerate(lever_ids):
                lever = self._find_lever(lid)
                if lever and lever.is_up:
                    value += 2 ** i
            if value == target:
                info["locked"] = False
                # Update terrain
                dx, dy = info["position"]
                if info.get("is_exit"):
                    self.grid[dy][dx].terrain = Terrain.EXIT
                else:
                    self.grid[dy][dx].terrain = Terrain.DOOR_OPEN
                return {"success": True, "message": f"The levers click into place. {door_id} unlocks!"}
            return {"success": False, "message": f"Nothing happens. (Current lever value: {value})"}

        return {"success": False, "message": f"Unknown puzzle type for {door_id}."}

    def _find_lever(self, lever_id: str) -> Optional[Lever]:
        for row in self.grid:
            for cell in row:
                for obj in cell.objects:
                    if isinstance(obj, Lever) and obj.id == lever_id:
                        return obj
        return None