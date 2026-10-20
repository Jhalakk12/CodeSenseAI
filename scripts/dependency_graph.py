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

    def generate_dot(
        self,
        selected_file: Optional[str] = None,
        show_symbols: bool = True,
        group_by_dir: bool = True,
        rankdir: str = "LR",
        focus_subgraph: bool = True
    ) -> str:
        """
        Generates Graphviz DOT syntax formatted for CodeSense AI dark DevOps aesthetics.
        When selected_file is provided and focus_subgraph is True, isolates the focused impact
        subgraph (target, callers, transitive dependents, and tests), eliminating visual clutter.
        """
        dot_lines = [
            "digraph CodeSenseTopology {",
            f'    graph [bgcolor="#0d1117" rankdir="{rankdir}" nodesep="0.6" ranksep="0.9" fontname="Helvetica" compound="true"];',
            '    node [shape="box" style="filled,rounded" fontname="Helvetica" fontsize="10" margin="0.2,0.15" penwidth="1.5"];',
            '    edge [color="#58a6ff" arrowsize="0.75" penwidth="1.2" fontname="Helvetica" fontsize="9" fontcolor="#8b949e"];'
        ]

        blast_data = None
        if selected_file:
            blast_data = self.get_blast_radius(selected_file)

        selected_mod = blast_data["target_file"] if blast_data else None
        direct_deps = set(blast_data["direct_dependents"]) if blast_data else set()
        transitive_deps = set(blast_data["transitive_dependents"]) if blast_data else set()
        upstream_imports = set(self.adj.get(selected_mod, set())) if selected_mod else set()

        if selected_file and focus_subgraph:
            def _rank_module(m: str) -> Tuple[int, str]:
                if "examples/" in m or "sample" in m:
                    return (2, m)
                if self.modules.get(m, {}).get("is_test") or "test" in m.lower():
                    return (1, m)
                return (0, m)

            # Prioritize direct dependents (callers), direct tests, key transitive, and upstreams
            direct_callers = sorted([d for d in direct_deps if not self.modules.get(d, {}).get("is_test", False) and "test" not in d.lower()], key=_rank_module)[:8]
            direct_tests = sorted([d for d in direct_deps if self.modules.get(d, {}).get("is_test", False) or "test" in d.lower()], key=_rank_module)[:4]
            transitive_callers = sorted([t for t in transitive_deps if not self.modules.get(t, {}).get("is_test", False) and "test" not in t.lower()], key=_rank_module)[:4]
            upstreams = sorted(list(upstream_imports), key=_rank_module)[:4]

            relevant_modules = {selected_mod} | set(direct_callers) | set(direct_tests) | set(transitive_callers) | set(upstreams)
            active_modules = [m for m in self.modules if m in relevant_modules]
            if selected_mod and selected_mod not in active_modules:
                active_modules.append(selected_mod)
        else:
            active_modules = list(self.modules.keys())

        active_set = set(active_modules)

        def _format_node_label(mod: str, meta: Dict[str, Any], tag: str = "") -> str:
            fname = os.path.basename(mod)
            lines_count = meta.get("line_count", 0)
            funcs = meta.get("functions", [])
            classes = meta.get("classes", [])

            label_lines = [fname]
            if tag:
                label_lines.append(f"[{tag}]")
            label_lines.append(f"({lines_count} lines)")

            if show_symbols and (funcs or classes):
                label_lines.append("----------------")
                if classes:
                    for c in classes[:2]:
                        label_lines.append(f"class {c}")
                    if len(classes) > 2:
                        label_lines.append(f"... +{len(classes)-2} classes")
                if funcs:
                    for f in funcs[:3]:
                        label_lines.append(f"def {f}()")
                    if len(funcs) > 3:
                        label_lines.append(f"... +{len(funcs)-3} funcs")

            return "\\n".join(label_lines)

        def _render_node_stmt(mod: str, meta: Dict[str, Any]) -> str:
            node_id = f'"{mod}"'
            is_test = meta.get("is_test", False) or "test" in mod.lower()

            if mod == selected_mod:
                label = _format_node_label(mod, meta, tag="Target Modified")
                return f'        {node_id} [label="{label}" fillcolor="#490202" color="#f85149" fontcolor="#ffffff" penwidth="2.5"];'
            elif mod in direct_deps:
                tag = "Affected Test (Direct)" if is_test else "Direct Impact"
                color = "#238636" if is_test else "#d29922"
                fill = "#042617" if is_test else "#3d2200"
                font = "#7ee787" if is_test else "#ffd280"
                style = "filled,rounded,dashed" if is_test else "filled,rounded"
                label = _format_node_label(mod, meta, tag=tag)
                return f'        {node_id} [label="{label}" fillcolor="{fill}" color="{color}" fontcolor="{font}" penwidth="2.0" style="{style}"];'
            elif mod in transitive_deps:
                tag = "Affected Test (Transitive)" if is_test else "Transitive Impact"
                color = "#2ea043" if is_test else "#9e6a03"
                fill = "#042617" if is_test else "#2b1900"
                font = "#7ee787" if is_test else "#e3b341"
                style = "filled,rounded,dashed" if is_test else "filled,rounded"
                label = _format_node_label(mod, meta, tag=tag)
                return f'        {node_id} [label="{label}" fillcolor="{fill}" color="{color}" fontcolor="{font}" penwidth="1.6" style="{style}"];'
            elif mod in upstream_imports:
                label = _format_node_label(mod, meta, tag="Upstream Dependency")
                return f'        {node_id} [label="{label}" fillcolor="#0b1b36" color="#388bfd" fontcolor="#79c0ff" penwidth="1.5"];'
            elif is_test:
                label = _format_node_label(mod, meta, tag="Test Suite")
                return f'        {node_id} [label="{label}" fillcolor="#0b1b36" color="#388bfd" fontcolor="#79c0ff" style="filled,rounded,dashed"];'
            else:
                label = _format_node_label(mod, meta)
                return f'        {node_id} [label="{label}" fillcolor="#161b22" color="#30363d" fontcolor="#c9d1d9"];'

        if group_by_dir:
            # Group active modules into folder clusters
            clusters: Dict[str, List[str]] = {}
            for mod in active_modules:
                folder = os.path.dirname(mod)
                cluster_key = folder if folder else "core"
                clusters.setdefault(cluster_key, []).append(mod)

            for c_key, mods in clusters.items():
                c_id = f"cluster_{c_key.replace('/', '_').replace('.', '_').replace('-', '_')}"
                c_title = f"Package: {c_key}/" if c_key != "core" else "Root Package"
                dot_lines.append(f'    subgraph "{c_id}" {{')
                dot_lines.append(f'        label="{c_title}";')
                dot_lines.append('        style="rounded,dashed";')
                dot_lines.append('        color="#30363d";')
                dot_lines.append('        fontcolor="#8b949e";')
                dot_lines.append('        fontsize="11";')
                dot_lines.append('        bgcolor="rgba(22, 27, 34, 0.4)";')
                for m in mods:
                    dot_lines.append(_render_node_stmt(m, self.modules.get(m, {})))
                dot_lines.append('    }')
        else:
            for mod in active_modules:
                dot_lines.append(_render_node_stmt(mod, self.modules.get(mod, {})))

        # Render Directed Edges restricted to active nodes
        include_edge_labels = (len(active_set) <= 25) or (selected_file and focus_subgraph)

        for src, targets in self.adj.items():
            if src not in active_set:
                continue
            for tgt in targets:
                if tgt not in active_set:
                    continue
                syms = self.symbol_imports.get((src, tgt), [])
                lbl = ""
                if include_edge_labels and syms:
                    lbl = f', label=" {syms[0]}"' if len(syms) == 1 else f', label=" {len(syms)} symbols"'
                
                if selected_mod and (src == selected_mod or tgt == selected_mod or src in direct_deps):
                    dot_lines.append(f'    "{src}" -> "{tgt}" [color="#f85149", penwidth="2.0"{lbl}];')
                else:
                    dot_lines.append(f'    "{src}" -> "{tgt}" [color="#388bfd"{lbl}];')

        dot_lines.append("}")
        return "\n".join(dot_lines)

    def generate_mermaid(
        self,
        selected_file: Optional[str] = None,
        direction: str = "LR",
        focus_subgraph: bool = True
    ) -> str:
        """
        Generates Mermaid flowchart diagram with folder subgraphs and risk color classes.
        When selected_file is provided and focus_subgraph is True, isolates the focused impact subgraph.
        """
        blast_data = self.get_blast_radius(selected_file) if selected_file else None
        selected_mod = blast_data["target_file"] if blast_data else None
        direct_deps = set(blast_data["direct_dependents"]) if blast_data else set()
        transitive_deps = set(blast_data["transitive_dependents"]) if blast_data else set()
        upstream_imports = set(self.adj.get(selected_mod, set())) if selected_mod else set()

        if selected_file and focus_subgraph:
            def _rank_module(m: str) -> Tuple[int, str]:
                if "examples/" in m or "sample" in m:
                    return (2, m)
                if self.modules.get(m, {}).get("is_test") or "test" in m.lower():
                    return (1, m)
                return (0, m)

            direct_callers = sorted([d for d in direct_deps if not self.modules.get(d, {}).get("is_test", False) and "test" not in d.lower()], key=_rank_module)[:8]
            direct_tests = sorted([d for d in direct_deps if self.modules.get(d, {}).get("is_test", False) or "test" in d.lower()], key=_rank_module)[:4]
            transitive_callers = sorted([t for t in transitive_deps if not self.modules.get(t, {}).get("is_test", False) and "test" not in t.lower()], key=_rank_module)[:4]
            upstreams = sorted(list(upstream_imports), key=_rank_module)[:4]

            relevant_modules = {selected_mod} | set(direct_callers) | set(direct_tests) | set(transitive_callers) | set(upstreams)
            active_modules = [m for m in self.modules if m in relevant_modules]
            if selected_mod and selected_mod not in active_modules:
                active_modules.append(selected_mod)
        else:
            active_modules = list(self.modules.keys())

        active_set = set(active_modules)
        lines = [f"graph {direction}"]

        # Group by folder subgraphs
        clusters: Dict[str, List[str]] = {}
        for mod in active_modules:
            folder = os.path.dirname(mod)
            cluster_key = folder if folder else "core"
            clusters.setdefault(cluster_key, []).append(mod)

        for c_key, mods in clusters.items():
            c_id = f"sub_{c_key.replace('/', '_').replace('.', '_').replace('-', '_')}"
            lines.append(f'    subgraph {c_id} ["📁 {c_key}/"]')
            for m in mods:
                m_id = m.replace("/", "_").replace(".", "_").replace("-", "_")
                fname = os.path.basename(m)
                lines.append(f'        {m_id}["📄 {fname}"]')
            lines.append("    end")

        for src, targets in self.adj.items():
            if src not in active_set:
                continue
            src_clean = src.replace("/", "_").replace(".", "_").replace("-", "_")
            for tgt in targets:
                if tgt not in active_set:
                    continue
                tgt_clean = tgt.replace("/", "_").replace(".", "_").replace("-", "_")
                lines.append(f"    {src_clean} --> {tgt_clean}")

        lines.append("    classDef default fill:#161b22,stroke:#30363d,stroke-width:1px,color:#c9d1d9;")
        lines.append("    classDef target fill:#490202,stroke:#f85149,stroke-width:3px,color:#ffffff;")
        lines.append("    classDef direct fill:#3d2200,stroke:#d29922,stroke-width:2px,color:#ffd280;")
        lines.append("    classDef transitive fill:#2b1900,stroke:#9e6a03,stroke-width:2px,color:#e3b341;")

        if selected_mod:
            s_clean = selected_mod.replace("/", "_").replace(".", "_").replace("-", "_")
            lines.append(f"    class {s_clean} target;")
            for d in direct_deps:
                d_clean = d.replace("/", "_").replace(".", "_").replace("-", "_")
                lines.append(f"    class {d_clean} direct;")
            for t in transitive_deps:
                t_clean = t.replace("/", "_").replace(".", "_").replace("-", "_")
                lines.append(f"    class {t_clean} transitive;")

        return "\n".join(lines)
