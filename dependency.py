import pandas as pd
import networkx as nx

# Load your CSV
df = pd.read_csv("dependency_data.csv")  # Replace with your filename

# Build directed graph from dependencies
G = nx.DiGraph()
for _, row in df.iterrows():
    G.add_edge(row["SourceTableName"], row["Target Table Name"])
try:
    cycles = list(nx.find_cycle(G, orientation='original'))
    if cycles:
        print("❌ Cycle detected in dependency graph:")
        for edge in cycles:
            print(" -> ".join(str(e[0]) for e in cycles + [cycles[0]]))
        raise Exception("Graph contains cycle. Topological sort cannot proceed.")
except nx.NetworkXNoCycle:
    print("✅ No cycle found. Proceeding with topological sort...")

# Step 1: Compute node levels (topological sort)
def calculate_node_levels(graph):
    levels = {}
    for node in nx.topological_sort(graph):
        preds = list(graph.predecessors(node))
        if preds:
            levels[node] = max(levels[p] for p in preds) + 1
        else:
            levels[node] = 1
    return levels

levels = calculate_node_levels(G)

# Step 2: Format node level as "X to Y"
def format_node_level(source, target):
    source_level = levels.get(source, 1)
    target_level = levels.get(target, source_level + 1)
    return f"{source_level} to {target_level}"

# Step 3: Find ultimate root(s) for each target
def find_ultimate_roots(graph, node):
    roots = []
    for root in [n for n in graph.nodes if graph.in_degree(n) == 0]:
        if nx.has_path(graph, root, node):
            roots.append(root)
    return ",".join(sorted(set(roots)))

# Step 4: Assign results to DataFrame
df["Node"] = df.apply(lambda row: format_node_level(row["SourceTableName"], row["Target Table Name"]), axis=1)
df["UltimateRoot"] = df["Target Table Name"].apply(lambda tgt: find_ultimate_roots(G, tgt))

# Step 5: Save to new CSV
df.to_csv("dependency_data_with_nodes_and_roots.csv", index=False)
print("✅ File saved as: dependency_data_with_nodes_and_roots.csv")
