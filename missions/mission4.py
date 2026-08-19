
def iterative_dfs(graph , start: str):
    if start not in graph:
        print(f"No location named {start} found in the kingdom")
        return

    visited = set()
    order = []
    stack = [start]

    while stack:
        current = stack.pop()

        if current in visited:
            continue

        visited.add(current)
        order.append(current)

        for nei_node in reversed(graph[current]):
            if nei_node not in visited:
                stack.append(nei_node)

    print(f"DFS Exploration:\n{(' -> '.join(order))}")
