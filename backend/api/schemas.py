"""Pydantic request models for the REST API."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ConfigModel(BaseModel):
    rows: int = Field(6, ge=1, le=12)
    cols: int = Field(7, ge=1, le=12)
    n: int = Field(4, ge=2, le=12)
    gravity: bool = True


class AgentSpecModel(BaseModel):
    kind: str = "alphabeta"
    depth: Optional[int] = Field(None, ge=1, le=8)
    simulations: Optional[int] = Field(None, ge=1, le=20000)
    seed: Optional[int] = None
    randomize_ties: bool = False
    name: Optional[str] = None


class NewGameRequest(BaseModel):
    config: ConfigModel = ConfigModel()
    first_player: int = Field(1, ge=1, le=2)


class GameStateRequest(NewGameRequest):
    moves: List[int] = []


class MoveRequest(GameStateRequest):
    move: int


class AIMoveRequest(GameStateRequest):
    agent: Optional[AgentSpecModel] = None
    difficulty: Optional[str] = None


class SeriesRequest(BaseModel):
    config: ConfigModel = ConfigModel()
    agent1: AgentSpecModel
    agent2: AgentSpecModel
    games: int = Field(10, ge=2, le=30)
    seed: int = 0
    opening_plies: int = Field(2, ge=0, le=8)
