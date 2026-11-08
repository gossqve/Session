"""Immutable topology declarations; EdgeState remains defined in core."""
from dataclasses import dataclass
from ..core.entities import identifier, number


@dataclass(frozen=True, slots=True)
class Area:
    area_id: str
    boundary_node: str

    def __post_init__(self):
        identifier(self.area_id)
        identifier(self.boundary_node)


@dataclass(frozen=True, slots=True)
class DirectedLink:
    link_id: str
    source_node: str
    target_node: str
    capacity_bps: float

    def __post_init__(self):
        for value in (self.link_id, self.source_node, self.target_node):
            identifier(value)
        number(self.capacity_bps, positive=True)


@dataclass(frozen=True, slots=True)
class FixedPath:
    path_id: str
    source_node: str
    target_node: str
    link_ids: tuple[str, ...]

    def __post_init__(self):
        for value in (self.path_id, self.source_node, self.target_node):
            identifier(value)
        if isinstance(self.link_ids, str):
            raise ValueError("link_ids must be an ordered sequence, not a string")
        object.__setattr__(self, "link_ids", tuple(self.link_ids))
        for value in self.link_ids:
            identifier(value)
