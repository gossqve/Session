"""Single static topology source shared by future network consumers.

Construction registers and validates a complete declaration atomically. No
dynamic registration, reverse inference, shortest path or future-plan state.
"""
from types import MappingProxyType
from ..core.entities import EdgeState, identifier
from .entities import Area, DirectedLink, FixedPath
from .validation import validate_link, validate_path


def _registry(objects, attribute, expected_type):
    result = {}
    for item in objects:
        if not isinstance(item, expected_type):
            raise ValueError(f"Expected {expected_type.__name__}")
        key = getattr(item, attribute)
        if key in result:
            raise ValueError(f"Duplicate {attribute}: {key}")
        result[key] = item
    return MappingProxyType(dict(sorted(result.items())))


def _pairs(values):
    result = []
    for pair in values:
        if isinstance(pair, str) or len(pair) != 2:
            raise ValueError("Expected source/target pair")
        for node in pair:
            identifier(node)
        result.append(tuple(pair))
    return tuple(sorted(set(result)))


class NetworkTopology:
    def __init__(self, *, areas, edges, links, paths, allowed_serving_pairs=(),
                 mobility_adjacency=None, mobility_transitions=()):
        self._areas = _registry(areas, "area_id", Area)
        self._edges = _registry(edges, "edge_id", EdgeState)
        nodes = {}
        for area in self.areas.values():
            if area.boundary_node in nodes:
                raise ValueError(f"Duplicate boundary node: {area.boundary_node}")
            nodes[area.boundary_node] = area.area_id
        for edge in self.edges.values():
            if edge.area_id not in self.areas:
                raise ValueError(f"Edge {edge.edge_id}: S2 requires a registered explicit Area")
            if edge.edge_id in nodes:
                raise ValueError(f"Edge/boundary namespace collision: {edge.edge_id}")
            nodes[edge.edge_id] = edge.area_id
        self._nodes = MappingProxyType(dict(sorted(nodes.items())))
        self._links = _registry(links, "link_id", DirectedLink)
        self._paths = _registry(paths, "path_id", FixedPath)
        by_pair = {}
        for path in self.paths.values():
            if path.path_id.startswith("@local/"):
                raise ValueError("@local/ path IDs are reserved for implicit empty local paths")
            pair = path.source_node, path.target_node
            if pair in by_pair:
                raise ValueError(f"Ambiguous fixed path for {pair}")
            by_pair[pair] = path
        self._by_pair = MappingProxyType(by_pair)
        self._allowed_serving_pairs = _pairs(allowed_serving_pairs)
        adjacency = {}
        for source, targets in (mobility_adjacency or {}).items():
            self._require_edge(source)
            if isinstance(targets, str):
                raise ValueError("Mobility neighbors must be an Edge sequence")
            adjacency[source] = frozenset(targets)
            for target in adjacency[source]:
                self._require_edge(target)
        self._mobility_adjacency = MappingProxyType(dict(sorted(adjacency.items())))
        self._mobility_transitions = _pairs(mobility_transitions)
        self.validate()

    @property
    def areas(self):
        return self._areas

    @property
    def edges(self):
        return self._edges

    @property
    def links(self):
        return self._links

    @property
    def paths(self):
        return self._paths

    @property
    def mobility_adjacency(self):
        return self._mobility_adjacency

    def node_area(self, node_id):
        if node_id not in self._nodes:
            raise ValueError(f"Unknown network node: {node_id}")
        return self._nodes[node_id]

    def edges_in_area(self, area_id):
        if area_id not in self.areas:
            raise ValueError(f"Unknown Area: {area_id}")
        return tuple(e.edge_id for e in self.edges.values() if e.area_id == area_id)

    def _require_edge(self, edge_id):
        if edge_id not in self.edges:
            raise ValueError(f"Unknown service Edge (boundary nodes cannot serve): {edge_id}")

    def get_path(self, source_node, target_node):
        self._require_edge(source_node)
        self._require_edge(target_node)
        path = self._by_pair.get((source_node, target_node))
        if path is not None:
            return path
        if source_node == target_node:
            return FixedPath(f"@local/{source_node}", source_node, target_node, ())
        raise ValueError(f"Missing configured directed fixed path: {source_node}->{target_node}")

    def validate_access_execution(self, access_edge_id, execution_edge_id):
        """Return independent uplink/downlink paths, or reject configuration."""
        return (self.get_path(access_edge_id, execution_edge_id),
                self.get_path(execution_edge_id, access_edge_id))

    def validate_serving_pairs(self):
        """All explicitly permitted initial/post-move pairs; no Cartesian guess."""
        for access, execution in self._allowed_serving_pairs:
            try:
                self.validate_access_execution(access, execution)
            except ValueError as exc:
                raise ValueError(f"Allowed Serving {access}/{execution}: {exc}") from exc
        return self._allowed_serving_pairs

    def validate_mobility_transitions(self):
        """Possible directed moves only, not a Markov sampler or Handover."""
        for source, target in self._mobility_transitions:
            self._require_edge(source)
            self._require_edge(target)
            if source != target and target not in self.mobility_adjacency.get(source, ()):
                raise ValueError(f"Mobility {source}->{target}: not a legal neighbor")
            self.get_path(source, target)
        return self._mobility_transitions

    def validate(self):
        for link in self.links.values():
            validate_link(link, self._nodes, self.edges, self.areas)
        for path in self.paths.values():
            validate_path(path, self.links, self.edges, self.areas)
        self.validate_serving_pairs()
        self.validate_mobility_transitions()

    @classmethod
    def from_config(cls, config, *, edges):
        """Use the caller's existing EdgeState objects, never construct a copy.

        Topology config Edge declarations must match that explicit registry.
        Workload/Session data is neither accepted nor retained here.
        """
        edges = tuple(edges)
        declared = {}
        for row in config["edges"]:
            if row["id"] in declared:
                raise ValueError(f"Duplicate configured Edge: {row['id']}")
            declared[row["id"]] = row["area_id"]
        if len(edges) != len(declared) or any(declared.get(e.edge_id) != e.area_id for e in edges):
            raise ValueError("Topology Edge declarations must match existing EdgeState registry")
        return cls(areas=[Area(**row) for row in config["areas"]], edges=edges,
                   links=[DirectedLink(**row) for row in config["links"]],
                   paths=[FixedPath(**row) for row in config["paths"]],
                   allowed_serving_pairs=config["allowed_serving_pairs"],
                   mobility_adjacency=config["mobility_adjacency"],
                   mobility_transitions=config["mobility_transitions"])
