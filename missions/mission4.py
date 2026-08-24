EXPLORATION_BONUS = 100

def iterative_dfs(graph, start: str):
    if start not in graph:
        print(f"No location named {start} found")
        return 0
    visited = {start}
    stack = [start]
    order = []
    while stack:
        current = stack.pop()
        order.append(current)
        for nei in reversed(graph[current]):
            if nei not in visited:
                visited.add(nei)
                stack.append(nei)
    print(f"DFS Exploration:\n{' -> '.join(order)}")
    return EXPLORATION_BONUS