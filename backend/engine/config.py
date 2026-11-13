"""Game configuration for the Connect-N engine."""
from __future__ import annotations

from dataclasses import dataclass

MAX_DIMENSION = 12


@dataclass(frozen=True)
class GameConfig:
    """Immutable description of a Connect-N variant.

    Attributes:
        rows, cols: board size (default 6 x 7).
        n: number of aligned tokens needed to win (default 4).
        gravity: ``True`` -> classic drop-a-token rules, a move is a *column*.
                 ``False`` -> free placement, a move is a *cell index* (row * cols + col).
    """

    rows: int = 6
    cols: int = 7
    n: int = 4
    gravity: bool = True

    def __post_init__(self) -> None:
        for name in ("rows", "cols", "n"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer, got {value!r}")
        if not (1 <= self.rows <= MAX_DIMENSION and 1 <= self.cols <= MAX_DIMENSION):
            raise ValueError(f"rows and cols must be between 1 and {MAX_DIMENSION}")
        if self.n < 2:
            raise ValueError("n must be at least 2")
        if self.n > max(self.rows, self.cols):
            raise ValueError(
                f"n={self.n} can never be reached on a {self.rows}x{self.cols} board"
            )

    @property
    def cells(self) -> int:
        return self.rows * self.cols

    @property
    def move_count(self) -> int:
        """Size of the move space (columns for gravity, cells for free placement)."""
        return self.cols if self.gravity else self.rows * self.cols

    def to_dict(self) -> dict:
        return {"rows": self.rows, "cols": self.cols, "n": self.n, "gravity": self.gravity}

    @classmethod
    def from_dict(cls, data: dict) -> "GameConfig":
        return cls(
            rows=int(data.get("rows", 6)),
            cols=int(data.get("cols", 7)),
            n=int(data.get("n", 4)),
            gravity=bool(data.get("gravity", True)),
        )
