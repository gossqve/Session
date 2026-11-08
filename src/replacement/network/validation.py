"""Model B.1 structural checks, with no routing or bandwidth allocation."""


def validate_link(link, nodes, edges, areas):
    source, target = link.source_node, link.target_node
    if source not in nodes or target not in nodes:
        raise ValueError(f"Link {link.link_id}: unregistered endpoint {source}->{target}")
    if source == target:
        raise ValueError(f"Link {link.link_id}: local Edge needs an empty path, not a self link")
    a, b = nodes[source], nodes[target]
    if a != b:
        valid = source == areas[a].boundary_node and target == areas[b].boundary_node
    else:
        valid = source in edges or target in edges
    if not valid:
        raise ValueError(f"Link {link.link_id}: illegal Area boundary connection {source}->{target}")


def validate_path(path, links, edges, areas):
    source, target = path.source_node, path.target_node
    if source not in edges or target not in edges:
        raise ValueError(f"Path {path.path_id}: end-to-end endpoints must be registered Edges")
    nodes = [source]
    for link_id in path.link_ids:
        if link_id not in links:
            raise ValueError(f"Path {path.path_id}: missing link {link_id}")
        link = links[link_id]
        if link.source_node != nodes[-1]:
            raise ValueError(f"Path {path.path_id}: discontinuity/direction error at {link_id}")
        nodes.append(link.target_node)
    if nodes[-1] != target:
        raise ValueError(f"Path {path.path_id}: wrong target {nodes[-1]}, expected {target}")
    a, b = edges[source].area_id, edges[target].area_id
    expected = ([source] if source == target else [source, target] if a == b else
                [source, areas[a].boundary_node, areas[b].boundary_node, target])
    if nodes != expected:
        raise ValueError(f"Path {path.path_id}: expected fixed direct Area path {expected}, got {nodes}")
