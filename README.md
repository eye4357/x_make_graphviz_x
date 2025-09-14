# x_make_graphviz_x

Rich Graphviz DOT builder with optional SVG rendering via the `graphviz` Python package.

Features:
- Directed/Undirected graphs; layout engine (dot, neato, fdp, sfdp, circo, twopi).
- Graph helpers and defaults:
  - graph_attr(rankdir="LR", splines="spline", overlap="false")
  - node_defaults(shape="box", style="filled", fillcolor="#eef", fontname="Consolas")
  - edge_defaults(color="#888", penwidth="2")
  - graph_label("My Graph", loc="t"), bgcolor("#ffffff")
  - rank([...]) for same-rank groups
- Nodes/Edges:
  - add_node("A", "Start", URL="https://example.com", tooltip="Go", fillcolor="#efe", style="filled")
  - add_edge("A","B","go", color="#1e90ff", URL="https://example.com/a-b")
  - Convenience: url/href keys map to Graphviz URL for SVG hyperlinks
  - record_label([...]) and html_label("...") helpers
  - image_node("Logo","logo.png", width="1", height="1")
  - Ports: add_edge("rec","rec", from_port="f0", to_port="f1")
- Subgraphs/Clusters:
  - sg = subgraph("cluster_0", cluster=True, label="Group"); sub_node(...); sub_edge(...)
- Advanced: add_raw("compound=true") to inject raw DOT.

Usage:
```python
from x_4357_make_graphviz_x.x_cls_make_graphviz_x import x_cls_make_graphviz_x as G

g = G(directed=True).rankdir("LR").node_defaults(shape="box")
g.graph_label("Pipeline", loc="t").bgcolor("#ffffff")
g.add_node("A","Start", style="filled", fillcolor="#efe", url="https://example.com")
g.add_node("B","End", style="filled", fillcolor="#fee")
g.add_edge("A","B","go", color="#1e90ff", tooltip="A to B")
g.save_dot("example.dot")
# Render SVG if python-graphviz and Graphviz binaries are available
g.to_svg("example")
```

SVG conversion:
- Install Graphviz system package and ensure `dot` is on PATH.
- Install Python package: `pip install graphviz`.
- In code: `g.to_svg("example")` -> writes example.svg. Or CLI: `dot -Tsvg example.dot -o example.svg`.
