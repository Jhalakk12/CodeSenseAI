"""
CodeSense AI - Inter-Module Dependency & Call Graph Visualizer ("Blast Radius")
Uses Python Abstract Syntax Tree (AST) static analysis to construct inter-module
dependency topologies, track cross-file invocations, and compute change impact (Blast Radius).
"""
import os
import ast
from collections import deque
from typing import Dict, Any, List, Set, Optional, Tuple


class DependencyGraph:
    """
    Parses a codebase using static AST analysis to construct module dependency
    networks and compute the 'Blast Radius' (downstream impact) of code changes.
    """
    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        self.modules: Dict[str, Dict[str, Any]] = {}
        # adj[A] = set of modules imported by A (A -> B means A depends on B)
        self.adj: Dict[str, Set[str]] = {}
        # rev_adj[B] = set of modules that import B (downstream dependents)
        self.rev_adj: Dict[str, Set[str]] = {}
        # symbol_imports: (source_mod, target_mod) -> list of imported symbols
        self.symbol_imports: Dict[Tuple[str, str], List[str]] = {}
        self.build_graph()

    def _normalize_mod_path(self, abs_path: str) -> str:
        """Converts an absolute file path to a clean relative POSIX path."""
        rel = os.path.relpath(abs_path, self.root_dir).replace("\\", "/")
        return rel

    def _get_python_files(self) -> List[str]:
        """Finds all non-virtualenv, non-cache Python source files."""
        py_files = []
        skip_dirs = {
            "__pycache__", "venv", ".venv", "env", ".git", ".pytest_cache",
            "chroma_db", "node_modules", "uploaded_repos", "cloned_repos"
        }
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in skip_dirs]
            for file in files:
                if file.endswith(".py"):
                    py_files.append(os.path.join(root, file))
        return py_files

    def _resolve_import_target(self, current_file: str, imported_module: str, level: int = 0) -> Optional[str]:
        """
        Resolves an AST import/from-import statement to an actual local repository file.
        Returns the relative POSIX path if the target is internal, else None (external library).
        """
        curr_dir = os.path.dirname(current_file)

        # 1. Handle relative imports (e.g. from . import foo, from ..auth import jwt)
        if level > 0:
            target_dir = curr_dir
            for _ in range(level - 1):
                target_dir = os.path.dirname(target_dir)

            if imported_module:
                parts = imported_module.split(".")
                candidate_py = os.path.join(target_dir, *parts) + ".py"
                candidate_init = os.path.join(target_dir, *parts, "__init__.py")
            else:
                candidate_py = ""
                candidate_init = os.path.join(target_dir, "__init__.py")

            if candidate_py and os.path.isfile(candidate_py):
                return self._normalize_mod_path(candidate_py)
            if os.path.isfile(candidate_init):
                return self._normalize_mod_path(candidate_init)

        # 2. Handle absolute project imports (e.g. auth.jwt_handler, services.deployment_service)
        parts = imported_module.split(".") if imported_module else []
        if parts:
            # Check relative to root_dir and known project subdirectories (sample_repo, src, etc.)
            search_roots = [
                self.root_dir,
                os.path.join(self.root_dir, "sample_repo"),
                os.path.join(self.root_dir, "src"),
                curr_dir
            ]
            for s_root in search_roots:
                cand_py = os.path.join(s_root, *parts) + ".py"
                cand_init = os.path.join(s_root, *parts, "__init__.py")
                if os.path.isfile(cand_py):
                    return self._normalize_mod_path(cand_py)
                if os.path.isfile(cand_init):
                    return self._normalize_mod_path(cand_init)

            # Suffix match against already registered modules
            rel_candidate = "/".join(parts) + ".py"
            for m in self.modules:
                if m.endswith(rel_candidate):
                    return m

        return None

    def build_graph(self):
        """Scans codebase and parses AST to populate dependency matrices."""
        py_files = self._get_python_files()

        for fpath in py_files:
            rel_mod = self._normalize_mod_path(fpath)
            self.modules[rel_mod] = {
                "functions": [],
                "classes": [],
                "line_count": 0,
                "is_test": "test" in os.path.basename(fpath).lower() or "tests/" in rel_mod
            }
            self.adj[rel_mod] = set()
            self.rev_adj[rel_mod] = set()

        for fpath in py_files:
            source_mod = self._normalize_mod_path(fpath)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                self.modules[source_mod]["line_count"] = len(content.splitlines())
                tree = ast.parse(content, filename=fpath)
            except Exception:
                continue

            for node in ast.walk(tree):
                # Function definitions
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.modules[source_mod]["functions"].append(node.name)
                # Class definitions
                elif isinstance(node, ast.ClassDef):
                    self.modules[source_mod]["classes"].append(node.name)
                # 'import foo' statements
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        target = self._resolve_import_target(fpath, alias.name, level=0)
                        if target and target in self.modules and target != source_mod:
                            self.adj[source_mod].add(target)
                            self.rev_adj[target].add(source_mod)
                            key = (source_mod, target)
                            self.symbol_imports.setdefault(key, []).append(alias.asname or alias.name)
                # 'from foo import bar' statements
                elif isinstance(node, ast.ImportFrom):
                    mod_name = node.module or ""
                    target = self._resolve_import_target(fpath, mod_name, level=node.level)
                    if not target and mod_name:
                        # Try matching top-level imported symbol as submodule
                        for alias in node.names:
                            sub_target = self._resolve_import_target(fpath, f"{mod_name}.{alias.name}", level=node.level)
                            if sub_target and sub_target in self.modules and sub_target != source_mod:
                                target = sub_target
                                break

                    if target and target in self.modules and target != source_mod:
                        self.adj[source_mod].add(target)
                        self.rev_adj[target].add(source_mod)
                        key = (source_mod, target)
                        syms = [a.name for a in node.names]
                        self.symbol_imports.setdefault(key, []).extend(syms)

    def get_blast_radius(self, target_file: str) -> Dict[str, Any]:
        """
        Computes the complete Blast Radius (downstream impact reachability) of changing target_file.
        Returns direct dependents, transitive dependents, impact percentage, risk rating, and tests.
        """
        clean_target = target_file.replace("\\", "/")
        # Match by relative path or basename
        matched_mod = None
        for mod in self.modules:
            if mod == clean_target or mod.endswith(clean_target) or clean_target.endswith(mod):
                matched_mod = mod
                break

        if not matched_mod:
            # Fallback if file not found in graph
            matched_mod = clean_target

        direct_dependents = sorted(list(self.rev_adj.get(matched_mod, set())))

        # BFS for transitive downstream reachability
        visited = set()
        queue = deque(direct_dependents)
        for dep in direct_dependents:
            visited.add(dep)

        transitive_only = set()
        while queue:
            curr = queue.popleft()
            for neighbor in self.rev_adj.get(curr, set()):
                if neighbor not in visited and neighbor != matched_mod:
                    visited.add(neighbor)
                    transitive_only.add(neighbor)
                    queue.append(neighbor)

        all_affected = sorted(list(visited))
        transitive_dependents = sorted(list(transitive_only))

        total_mods = max(1, len(self.modules))
        impact_ratio = len(all_affected) / total_mods

        # Determine change risk tier
        if impact_ratio >= 0.50 or any("auth" in matched_mod or "connection" in matched_mod for _ in [1]):
            risk_level = "CRITICAL"
        elif impact_ratio >= 0.25:
            risk_level = "HIGH"
        elif len(all_affected) > 0:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        # Filter affected regression tests
        affected_tests = [m for m in all_affected if self.modules.get(m, {}).get("is_test", False)]
        impacted_services = [m for m in all_affected if not self.modules.get(m, {}).get("is_test", False)]

        recommendations = []
        if affected_tests:
            recommendations.append(f"Execute regression test suites: {', '.join(affected_tests)}")
        else:
            recommendations.append(f"No existing test suites directly cover downstream dependents of `{matched_mod}`. Generate tests via CodeSense AI Test Mode.")

        if impacted_services:
            recommendations.append(f"Review contract / API breaking changes in: {', '.join(impacted_services[:3])}")

        return {
            "target_file": matched_mod,
            "direct_dependents": direct_dependents,
            "transitive_dependents": transitive_dependents,
            "all_affected": all_affected,
            "total_affected_count": len(all_affected),
            "total_modules": total_mods,
            "impact_percentage": round(impact_ratio * 100, 1),
            "risk_level": risk_level,
            "affected_tests": affected_tests,
            "impacted_services": impacted_services,
            "recommendations": recommendations,
            "functions": self.modules.get(matched_mod, {}).get("functions", []),
            "classes": self.modules.get(matched_mod, {}).get("classes", [])
        }

    def generate_dot(self, selected_file: Optional[str] = None) -> str:
        """
        Generates Graphviz DOT syntax formatted for CodeSense AI dark DevOps aesthetics.
        Colors:
          - Selected target: #f85149 (Coral Red)
          - Direct dependents: #d29922 (Amber Gold)
          - Transitive dependents: #bb8009 (Muted Gold)
          - Unaffected modules: #1f6feb / #30363d (Navy/Slate)
        """
        dot_lines = [
            "digraph CodeSenseTopology {",
            '    graph [bgcolor="#0d1117" rankdir="LR" nodesep="0.6" ranksep="1.0" fontname="Helvetica"];',
            '    node [shape="box" style="filled,rounded" fontname="Helvetica" fontsize="11" margin="0.25,0.15" penwidth="1.5"];',
            '    edge [color="#58a6ff" arrowsize="0.75" penwidth="1.2" fontname="Helvetica" fontsize="9" fontcolor="#8b949e"];'
        ]

        blast_data = None
        if selected_file:
            blast_data = self.get_blast_radius(selected_file)

        selected_mod = blast_data["target_file"] if blast_data else None
        direct_deps = set(blast_data["direct_dependents"]) if blast_data else set()
        transitive_deps = set(blast_data["transitive_dependents"]) if blast_data else set()

        # Render Nodes
        for mod, meta in self.modules.items():
            node_id = f'"{mod}"'
            label = os.path.basename(mod)
            sub = os.path.dirname(mod)
            display_label = f"{sub}/\\n{label}" if sub else label

            if mod == selected_mod:
                # Target: Hot Coral Red
                dot_lines.append(
                    f'    {node_id} [label="{display_label}\\n(🎯 Target Modified)" fillcolor="#490202" color="#f85149" fontcolor="#ffffff" penwidth="2.5"];'
                )
            elif mod in direct_deps:
                # Direct downstream impact: Amber Orange
                dot_lines.append(
                    f'    {node_id} [label="{display_label}\\n(💥 Direct Impact)" fillcolor="#3d2200" color="#d29922" fontcolor="#ffd280" penwidth="2.0"];'
                )
            elif mod in transitive_deps:
                # Transitive downstream impact: Muted Amber
                dot_lines.append(
                    f'    {node_id} [label="{display_label}\\n(⚠️ Transitive Impact)" fillcolor="#2b1900" color="#9e6a03" fontcolor="#e3b341"];'
                )
            elif meta.get("is_test"):
                # Test modules: Cyan dashed
                dot_lines.append(
                    f'    {node_id} [label="{display_label}\\n(🧪 Test Suite)" fillcolor="#0b1b36" color="#388bfd" fontcolor="#79c0ff" style="filled,rounded,dashed"];'
                )
            else:
                # Normal unimpacted module: Slate Blue
                dot_lines.append(
                    f'    {node_id} [label="{display_label}" fillcolor="#161b22" color="#30363d" fontcolor="#c9d1d9"];'
                )

        # Render Directed Edges (A -> B means A imports B)
        for src, targets in self.adj.items():
            for tgt in targets:
                # Highlight edge if it connects into or out of blast radius
                if selected_mod and (src == selected_mod or tgt == selected_mod or src in direct_deps):
                    dot_lines.append(f'    "{src}" -> "{tgt}" [color="#f85149" penwidth="2.0"];')
                else:
                    dot_lines.append(f'    "{src}" -> "{tgt}" [color="#30363d"];')

        dot_lines.append("}")
        return "\n".join(dot_lines)

    def generate_mermaid(self, selected_file: Optional[str] = None) -> str:
        """Generates Mermaid flowchart diagram (graph LR) with risk color classes."""
        blast_data = self.get_blast_radius(selected_file) if selected_file else None
        selected_mod = blast_data["target_file"] if blast_data else None
        direct_deps = set(blast_data["direct_dependents"]) if blast_data else set()

        lines = ["graph LR"]
        for src, targets in self.adj.items():
            src_clean = src.replace("/", "_").replace(".", "_").replace("-", "_")
            for tgt in targets:
                tgt_clean = tgt.replace("/", "_").replace(".", "_").replace("-", "_")
                lines.append(f"    {src_clean}[{os.path.basename(src)}] --> {tgt_clean}[{os.path.basename(tgt)}]")

        lines.append("    classDef default fill:#161b22,stroke:#30363d,stroke-width:1px,color:#c9d1d9;")
        lines.append("    classDef target fill:#490202,stroke:#f85149,stroke-width:3px,color:#ffffff;")
        lines.append("    classDef direct fill:#3d2200,stroke:#d29922,stroke-width:2px,color:#ffd280;")

        if selected_mod:
            s_clean = selected_mod.replace("/", "_").replace(".", "_").replace("-", "_")
            lines.append(f"    class {s_clean} target;")
            for d in direct_deps:
                d_clean = d.replace("/", "_").replace(".", "_").replace("-", "_")
                lines.append(f"    class {d_clean} direct;")

        return "\n".join(lines)
