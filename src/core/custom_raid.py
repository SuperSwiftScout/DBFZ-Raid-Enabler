"""Custom raid definition and JSON persistence."""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional
from utils.errors import DBFZRaidError
from utils.logger import logger

CUSTOM_RAIDS_DIR = Path.home() / ".dbfz_raid_enabler" / "custom_raids"


@dataclass
class RaidBattle:
    """Single battle within a raid (one of 7 rounds)."""
    battle_no: int       # 0-6
    char1: str           # Boss character code
    char2: str           # Support character code
    char3: str           # Support character code
    level: int           # Character level (1-100)
    skill_num: int       # Skill set ID
    background: str      # Stage background ID
    bgm: str             # Music track ID


@dataclass
class CustomRaid:
    """Full custom raid definition (7 battles)."""
    name: str
    battles: List[RaidBattle] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CustomRaid":
        battles = [RaidBattle(**b) for b in data["battles"]]
        return cls(name=data["name"], battles=battles)

    def is_complete(self) -> bool:
        return len(self.battles) == 7

    def save(self, path: Optional[Path] = None) -> Path:
        """Save raid to JSON file. Returns path written."""
        if path is None:
            CUSTOM_RAIDS_DIR.mkdir(parents=True, exist_ok=True)
            safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in self.name)
            path = CUSTOM_RAIDS_DIR / f"{safe_name}.json"

        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        logger.info(f"Custom raid saved to {path}")
        return path

    @classmethod
    def load(cls, path: Path) -> "CustomRaid":
        """Load raid from JSON file."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls.from_dict(data)
        except Exception as e:
            raise DBFZRaidError(f"Failed to load custom raid from {path}: {e}")


def list_saved_raids() -> List[Path]:
    """Return all saved custom raid JSON files."""
    if not CUSTOM_RAIDS_DIR.exists():
        return []
    return sorted(CUSTOM_RAIDS_DIR.glob("*.json"))
