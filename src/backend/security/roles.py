"""Role based access rules for the NeuroPit gateway.

The PRD lists five primary users. We map them to four roles because the data
engineer view and the sports neuroscientist view need the same scopes for
V1. If that assumption changes, split them here first.

Each scope is a coarse label rather than a fine grained permission. The
gateway uses these scopes to decide whether a route is allowed for a given
token. Adding a new scope is a single line change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Set


@dataclass(frozen=True)
class Role:
    name: str
    description: str
    scopes: Set[str]


_ROLES: Dict[str, Role] = {
    "team_principal": Role(
        name="team_principal",
        description="Final decision maker on race strategy with full read access and strategy override.",
        scopes={
            "read:cognitive",
            "read:explanation",
            "read:strategy",
            "write:strategy_override",
            "read:audit",
            "read:prescription",
            "read:whatif",
        },
    ),
    "race_strategist": Role(
        name="race_strategist",
        description="Operates the strategy parliament during the race.",
        scopes={
            "read:cognitive",
            "read:explanation",
            "read:strategy",
            "write:counterfactual",
            "read:prescription",
            "write:prescription_preview",
            "read:whatif",
            "write:whatif",
        },
    ),
    "driver_engineer": Role(
        name="driver_engineer",
        description="Driver performance engineer working with cognitive and telemetry signals.",
        scopes={"read:cognitive", "read:telemetry", "read:ghost_lap", "read:prescription"},
    ),
    "neuro_analyst": Role(
        name="neuro_analyst",
        description="Sports neuroscientist or data engineer performing offline analysis.",
        scopes={
            "read:cognitive",
            "read:telemetry",
            "read:audit",
            "read:ghost_lap",
            "read:prescription",
            "read:whatif",
            "write:whatif",
        },
    ),
}


def get_role(name: str) -> Role:
    if name not in _ROLES:
        raise KeyError(f"Unknown role {name!r}. Allowed: {sorted(_ROLES)}")
    return _ROLES[name]


def list_roles() -> Iterable[Role]:
    return _ROLES.values()


def has_scope(role_name: str, scope: str) -> bool:
    try:
        return scope in get_role(role_name).scopes
    except KeyError:
        return False
