"""Graph utilities shared across backend services."""

from collections import deque


def find_ancestors(node_id: str, edges: list[dict]) -> set[str]:
    """Find all ancestor node IDs for a given node.

    Args:
        node_id: The node whose ancestors to find.
        edges: List of edge dicts with ``"source"`` and ``"target"`` keys.

    Returns:
        Set of ancestor node IDs (does not include *node_id* itself).
    """
    parents: dict[str, list[str]] = {}
    for edge in edges:
        parents.setdefault(edge["target"], []).append(edge["source"])

    ancestors: set[str] = set()
    stack = list(parents.get(node_id, []))

    while stack:
        current = stack.pop()
        if current not in ancestors:
            ancestors.add(current)
            stack.extend(parents.get(current, []))

    return ancestors


def topological_sort(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Kahn's algorithm for topological ordering.

    Args:
        nodes: List of node dicts, each containing at least an ``"id"`` key.
        edges: List of edge dicts with ``"source"`` and ``"target"`` keys.

    Returns:
        Node IDs in topological order.

    Raises:
        ValueError: If the graph contains a cycle.
    """
    in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}
    adjacency: dict[str, list[str]] = {n["id"]: [] for n in nodes}

    for edge in edges:
        adjacency[edge["source"]].append(edge["target"])
        in_degree[edge["target"]] += 1

    queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
    result: list[str] = []

    while queue:
        node_id = queue.popleft()
        result.append(node_id)
        for neighbor in adjacency[node_id]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(nodes):
        raise ValueError("Workflow DAG contains a cycle")

    return result
