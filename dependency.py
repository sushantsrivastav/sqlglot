import pandas as pd
import networkx as nx

# Load input CSV
df = pd.read_csv("dependency_data.csv")  # replace with your filename

# Create fully qualified names
df["SourceFull"] = df["Source DB Name"] + "." + df["Source Schema Name"] + "." + df["SourceTableName"]
df["TargetFull"] = df["Target DB Name"] + "." + df["Target Schema Name"] + "." + df["Target Table Name"]

# Build the directed graph
G = nx.DiGraph()
for _, row in df.iterrows():
    G.add_edge(row["SourceFull"], row["TargetFull"])

# Optional: Detect cycles before proceeding
try:
    cycles = list(nx.find_cycle(G, orientation='original'))
    if cycles:
        print("❌ Cycle detected:")
        print(" -> ".join(str(edge[0]) for edge in cycles + [cycles[0]]))
        raise Exception("Graph contains a cycle. Cannot proceed with topological sort.")
except nx.NetworkXNoCycle:
    print("✅ No cycles detected.")

# Compute levels via topological sort
def calculate_node_levels(graph):
    levels = {}
    for node in nx.topological_sort(graph):
        preds = list(graph.predecessors(node))
        levels[node] = max([levels[p] for p in preds], default=0) + 1
    return levels

levels = calculate_node_levels(G)

# Assign Node (level transition) and UltimateRoot
def format_node_level(src, tgt):
    return f"{levels.get(src, 1)} to {levels.get(tgt, 2)}"

def find_roots(node):
    root_nodes = [n for n in G.nodes if G.in_degree(n) == 0]
    return ",".join(sorted(r for r in root_nodes if nx.has_path(G, r, node)))

# Add results to DataFrame
df["Node"] = df.apply(lambda row: format_node_level(row["SourceFull"], row["TargetFull"]), axis=1)
df["UltimateRoot"] = df["TargetFull"].apply(find_roots)

# Optional: Save updated output
df.to_csv("dependency_data_with_nodes_and_roots.csv", index=False)
print("✅ Saved: dependency_data_with_nodes_and_roots.csv")
