"""
Unit tests for Feature 4: Inter-Module Dependency & Call Graph Visualizer ("Blast Radius").
Validates AST import parsing, reverse dependency reachability, cyclic resilience, and DOT export.
"""
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.dependency_graph import DependencyGraph


def test_dependency_graph_parsing():
    """Verify that DependencyGraph successfully parses sample_repo and detects functions/classes."""
    graph = DependencyGraph("sample_repo")
    assert len(graph.modules) >= 4

    # Check that auth/jwt_handler.py is registered
    jwt_key = [m for m in graph.modules if "jwt_handler" in m][0]
    meta = graph.modules[jwt_key]
    assert "create_access_token" in meta["functions"]
    assert "verify_token" in meta["functions"]
    assert meta["line_count"] > 10


def test_dependency_graph_imports():
    """Verify that AST extracts imports and populates both forward and reverse adjacency lists."""
    graph = DependencyGraph("sample_repo")

    jwt_mod = [m for m in graph.modules if "jwt_handler" in m][0]
    routes_mod = [m for m in graph.modules if "routes" in m][0]

    # routes.py imports jwt_handler.py
    assert jwt_mod in graph.adj[routes_mod]
    # jwt_handler.py should have routes.py in its reverse adjacency
    assert routes_mod in graph.rev_adj[jwt_mod]


def test_blast_radius_calculation():
    """Verify that get_blast_radius identifies downstream impacted files and calculates risk."""
    graph = DependencyGraph("sample_repo")
    blast = graph.get_blast_radius("auth/jwt_handler.py")

    assert blast["target_file"] == "auth/jwt_handler.py" or blast["target_file"].endswith("jwt_handler.py")
    assert any("routes.py" in dep for dep in blast["direct_dependents"])
    assert blast["total_affected_count"] >= 1
    assert blast["impact_percentage"] > 0
    assert blast["risk_level"] in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    assert len(blast["recommendations"]) > 0


def test_cyclic_dependency_resilience():
    """Verify that circular imports do not cause infinite recursion in blast radius BFS."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_a = os.path.join(tmp_dir, "module_a.py")
        file_b = os.path.join(tmp_dir, "module_b.py")

        with open(file_a, "w", encoding="utf-8") as f:
            f.write("import module_b\ndef func_a():\n    return module_b.func_b()\n")

        with open(file_b, "w", encoding="utf-8") as f:
            f.write("import module_a\ndef func_b():\n    return module_a.func_a()\n")

        cyclic_graph = DependencyGraph(tmp_dir)
        blast_a = cyclic_graph.get_blast_radius("module_a.py")

        # Must terminate safely and identify circular dependent
        assert "module_b.py" in blast_a["direct_dependents"]
        assert blast_a["total_affected_count"] == 1


def test_dot_and_mermaid_generation():
    """Verify that Graphviz DOT and Mermaid strings contain proper syntax and highlight nodes."""
    graph = DependencyGraph("sample_repo")
    dot = graph.generate_dot(selected_file="auth/jwt_handler.py")

    assert "digraph CodeSenseTopology" in dot
    assert "bgcolor=\"#0d1117\"" in dot
    assert "🎯 Target Modified" in dot
    assert "💥 Direct Impact" in dot

    mermaid = graph.generate_mermaid(selected_file="auth/jwt_handler.py")
    assert mermaid.startswith("graph LR")
    assert "classDef target" in mermaid


def test_cli_execute_blast_and_topology(capsys):
    """Verify that CLI execute_blast_radius and execute_topology print structured output."""
    from cli import execute_blast_radius, execute_topology

    execute_blast_radius("auth/jwt_handler.py", root_dir="sample_repo")
    captured = capsys.readouterr().out
    assert "BLAST RADIUS IMPACT REPORT" in captured
    assert "Risk Level" in captured
    assert "api/routes.py" in captured

    execute_topology("sample_repo")
    topo_out = capsys.readouterr().out
    assert "REPOSITORY DEPENDENCY TOPOLOGY" in topo_out
    assert "routes.py" in topo_out

