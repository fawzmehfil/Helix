import datetime as dt

from helix.graph_engine import ComputationGraph, GraphNode


def test_graph_add_find(graph_db_path):
    graph = ComputationGraph(graph_db_path)
    node = GraphNode("n", "s", "r", "i", "o", {"content": "x"}, 1, 1, 1.0, "fake", dt.datetime.utcnow())
    graph.add_node(node)
    assert graph.find_node("i", "fake").node_id == "n"
    assert graph.stats()["total_nodes"] == 1

