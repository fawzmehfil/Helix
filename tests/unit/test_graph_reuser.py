import datetime as dt

from helix.context_engine import ContextDecomposer, SemanticHasher
from helix.graph_engine import ComputationGraph, GraphNode, GraphReuser


def test_graph_reuser(graph_db_path):
    graph = ComputationGraph(graph_db_path)
    snap = ContextDecomposer(SemanticHasher()).decompose_string("hello", "s", "r")
    graph.add_node(GraphNode("n", "s", "r", snap.composite_hash, "o", {}, 1, 1, 1, "fake", dt.datetime.now(dt.UTC)))
    assert GraphReuser(graph).find_reusable_node(snap, "fake").node_id == "n"
