#!/usr/bin/env python3
"""Portable helpers for Codex Modernize. Python 3.10+, standard library only.

Copyright 2026 DevilsNerve. New adaptation code under LICENSE.md.
Batch ordering derives from Anthropic's Apache-2.0 workflow design; changed to a
read-only planner with explicit completed dependencies and filesystem validation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SYSTEM_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")
NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
WINDOWS_RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?\Z", re.I)
MARKER = "/*__TOPOLOGY_DATA__*/ null"
STAGES = {
    "preflight": ["PREFLIGHT.md"],
    "assess": ["ASSESSMENT.md", "ARCHITECTURE.mmd"],
    "map": ["topology.json", "TOPOLOGY.html"],
    "extract-rules": ["BUSINESS_RULES.md", "DATA_OBJECTS.md"],
    "brief": ["MODERNIZATION_BRIEF.md"],
    "harden": ["SECURITY_FINDINGS.md", "security_remediation.patch"],
    "uplift": ["DELTA_CATALOG.md", "BASELINE.md", "PLAYBOOK.md"],
}


class ValidationError(ValueError):
    """An input is incomplete or would escape the intended operation."""


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def no_links(path: Path, root: Path) -> Path:
    """Validate a lexical output path, including existing parent components."""
    require(inside(path, root), f"Output is outside workspace: {path}")
    current = root
    for part in path.relative_to(root).parts:
        require(part not in (".", ".."), "Traversal is not an output path")
        current = current / part
        require(not current.is_symlink(), f"Output cannot follow a symlink: {current}")
        require(not getattr(current, "is_junction", lambda: False)(),
                f"Output cannot follow a junction: {current}")
        require(current.resolve() == current, f"Output cannot follow a filesystem alias: {current}")
    require(inside(path.resolve(), root), f"Output resolves outside workspace: {path}")
    return path


class Workspace:
    def __init__(self, root, system):
        require(isinstance(system, str) and SYSTEM_RE.fullmatch(system),
                "System must match [A-Za-z0-9][A-Za-z0-9_-]*")
        require(not WINDOWS_RESERVED.fullmatch(system), "Reserved system directory name")
        self.root = Path(root).expanduser().resolve(strict=True)
        require(self.root.is_dir(), "Workspace must be an existing directory")
        self.system = system
        self.source = (self.root / "legacy" / system).resolve()
        self.analysis = self.output(f"analysis/{system}")
        self.uplift = self.output(f"modernized/{system}-uplifted")
        self.transform = self.output(f"modernized/{system}")
        self.reimagine = self.output(f"modernized/{system}-reimagined")

    def output(self, relative):
        result = no_links(self.root / relative, self.root)
        # Check the whole output area, not only one system's subdirectory.
        area = self.root / Path(relative).parts[0]
        require(not inside(result.resolve(), self.source)
                and not inside(self.source, area.resolve()),
                "Source and output areas overlap")
        return result

    def require_source(self):
        require(self.source.is_dir(), f"Source directory does not exist: {self.source}")

    def as_dict(self):
        return {"workspace": str(self.root), "system": self.system,
                "source": str(self.source), "sourceExists": self.source.is_dir(),
                "analysis": str(self.analysis), "transform": str(self.transform),
                "reimagine": str(self.reimagine), "uplift": str(self.uplift)}


def reject_constant(value):
    raise ValidationError(f"Invalid JSON number: {value}")


def load_json(path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle, parse_constant=reject_constant)


def atomic_text(path: Path, content: str):
    """Replace a validated output without leaving a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def validate_topology(data):
    require(isinstance(data, dict), "Topology must be an object")
    require(isinstance(data.get("system"), str), "Topology needs a system name")
    ids, leaves = set(), set()

    def walk(node, depth=0):
        require(depth <= 100 and isinstance(node, dict), "Invalid or excessively deep node")
        nid = node.get("id")
        require(isinstance(nid, str) and nid, "Every node needs a nonempty string id")
        require(nid not in ids, f"Duplicate topology id: {nid}")
        ids.add(nid)
        require(isinstance(node.get("name"), str), f"Node {nid} needs a name")
        require(node.get("kind") in ("system", "domain", "module", "datastore", "job", "screen"),
                f"Unknown node kind for {nid}")
        children = node.get("children", [])
        require(isinstance(children, list), f"Children of {nid} must be a list")
        if children:
            require(node["kind"] in ("system", "domain"), f"Leaf {nid} cannot contain children")
            for child in children:
                walk(child, depth + 1)
        else:
            leaves.add(nid)
        if "loc" in node:
            loc = node["loc"]
            require(type(loc) in (int, float) and math.isfinite(loc) and loc >= 0,
                    f"Invalid LOC for {nid}")
        for field in ("language", "file"):
            if field in node:
                require(isinstance(node[field], str), f"{field} of {nid} must be a string")

    walk(data.get("root"))
    require(data["root"]["kind"] == "system", "Root kind must be system")
    edges = data.get("edges", [])
    require(isinstance(edges, list), "Edges must be a list")
    for edge in edges:
        require(isinstance(edge, dict), "Edge must be an object")
        for endpoint in ("source", "target"):
            require(isinstance(edge.get(endpoint), str) and edge[endpoint] in leaves,
                    f"Edge {endpoint} must reference an existing leaf")
        require(edge.get("kind") in ("call", "dispatch", "read", "write"), "Unknown edge kind")
    for key in ("entryPoints", "deadEnds"):
        refs = data.get(key, [])
        require(isinstance(refs, list) and all(isinstance(x, str) and x in leaves for x in refs),
                f"{key} must reference existing leaves")
    observations = data.get("observations", [])
    require(isinstance(observations, list) and all(isinstance(x, str) for x in observations),
            "Observations must be strings")
    flows = data.get("flows", [])
    require(isinstance(flows, list), "Flows must be a list")
    for flow in flows:
        require(isinstance(flow, dict) and isinstance(flow.get("name"), str), "Flow needs a name")
        for key in ("persona", "description"):
            require(isinstance(flow.get(key, ""), str), f"Flow {key} must be a string")
        steps = flow.get("steps")
        require(isinstance(steps, list), "Flow needs a steps list")
        for step in steps:
            require(isinstance(step, dict) and isinstance(step.get("label"), str), "Step needs a label")
            nodes = step.get("nodes", [])
            require(isinstance(nodes, list) and all(isinstance(x, str) and x in ids for x in nodes),
                    "Flow step references an unknown node")
    return {"nodes": len(ids), "edges": len(edges), "flows": len(flows)}


def render_topology(ws):
    src = ws.output(f"analysis/{ws.system}/topology.json")
    dst = ws.output(f"analysis/{ws.system}/TOPOLOGY.html")
    data = load_json(src)
    counts = validate_topology(data)
    template = (PLUGIN_ROOT / "assets/topology-viewer.html").read_text(encoding="utf-8")
    require(template.count(MARKER) == 1, "Viewer must have exactly one data marker")
    encoded = json.dumps(data, ensure_ascii=True, allow_nan=False)
    for char, escaped in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026")):
        encoded = encoded.replace(char, escaped)
    atomic_text(dst, template.replace(MARKER, "/*__TOPOLOGY_DATA__*/ " + encoded))
    return {"output": str(dst), **counts}


def copy_source(ws):
    ws.require_source()
    require(not ws.uplift.exists(), f"Refusing to overwrite existing copy: {ws.uplift}")
    excluded = {".git", ".hg", ".svn", "CVS", "__pycache__"}

    def check_tree(path, ancestors):
        actual = path.resolve(strict=True)
        require(inside(actual, ws.source), f"Source link leaves the system: {path}")
        if actual.is_dir():
            require(actual not in ancestors, f"Source contains a symlink cycle: {path}")
            for item in actual.iterdir():
                if item.name not in excluded:
                    check_tree(item, ancestors | {actual})
        else:
            require(actual.is_file(), f"Cannot copy special source file: {path}")

    check_tree(ws.source, set())
    ws.uplift.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{ws.system}-copy-", dir=ws.uplift.parent))
    try:
        shutil.copytree(ws.source, staging / "tree", symlinks=False,
                        ignore=shutil.ignore_patterns(*excluded))
        require(not ws.uplift.exists(), "Destination appeared during copy; refusing overwrite")
        (staging / "tree").rename(ws.uplift)
    finally:
        shutil.rmtree(staging)
    return {"source": str(ws.source), "copy": str(ws.uplift), "legacyModified": False}


def unit_path(raw):
    require(isinstance(raw, str) and 0 < len(raw) <= 400, "Unit path must be a relative directory")
    raw = raw.replace("\\", "/")
    require(not raw.startswith("/") and not re.match(r"^[A-Za-z]:", raw), "Absolute unit path")
    parts = [p for p in raw.split("/") if p not in ("", ".")]
    require(parts, "A unit cannot own the working-copy root")
    for part in parts:
        require(part != ".." and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_. -]*", part)
                and not part.endswith((".", " ")) and not WINDOWS_RESERVED.fullmatch(part),
                f"Unsafe unit path component: {part}")
    return "/".join(parts)


def plan_batch(ws, plan):
    require(isinstance(plan, dict) and isinstance(plan.get("units"), list), "Plan needs units")
    units, names, paths = [], set(), []
    for unit in plan["units"]:
        require(isinstance(unit, dict), "Unit must be an object")
        name = unit.get("name")
        require(isinstance(name, str) and NAME_RE.fullmatch(name), "Invalid unit name")
        require(name.casefold() not in {n.casefold() for n in names}, "Duplicate unit name")
        names.add(name)
        path = unit_path(unit.get("path"))
        ws.output(f"modernized/{ws.system}-uplifted/{path}")
        lower = path.casefold()
        require(all(lower != p and not lower.startswith(p + "/") and not p.startswith(lower + "/")
                    for p in paths), "Unit paths overlap")
        paths.append(lower)
        deps = unit.get("deps")
        require(isinstance(deps, list) and all(isinstance(d, str) and NAME_RE.fullmatch(d) for d in deps),
                f"Unit {name} needs an explicit deps list")
        require(name not in deps, f"Unit {name} depends on itself")
        units.append({"name": name, "path": path, "deps": list(dict.fromkeys(deps))})
    completed = plan.get("completed", [])
    require(isinstance(completed, list) and all(isinstance(n, str) and NAME_RE.fullmatch(n) for n in completed),
            "Completed must contain external dependency names")
    require(len(set(completed)) == len(completed) and not names.intersection(completed),
            "Completed names must be unique and outside units")
    for unit in units:
        require(set(unit["deps"]) <= names | set(completed), f"Unknown dependency in {unit['name']}")
    ordered = set(completed)
    while True:
        ready = {u["name"] for u in units if set(u["deps"]) <= ordered}
        if ready <= ordered:
            break
        ordered.update(ready)
    require(names <= ordered, "Dependency cycle; choose a coordinated cut")
    results = plan.get("results", [])
    require(isinstance(results, list), "Results must be a list")
    by_name = {}
    for result in results:
        require(isinstance(result, dict) and isinstance(result.get("unit"), str)
                and result["unit"] in names, "Result names an unknown unit")
        name = result["unit"]
        require(name not in by_name, f"Duplicate result for {name}")
        require(type(result.get("buildRan")) is bool and type(result.get("built")) is bool,
                "Build results need boolean buildRan and built")
        if result["buildRan"]:
            require(isinstance(result.get("buildCommand"), str) and result["buildCommand"].strip(),
                    "An executed build needs its command")
        require(not result["built"] or result["buildRan"], "Cannot claim built without running a build")
        by_name[name] = result
    built = {name for name, result in by_name.items() if result["built"]}
    failed = set(by_name) - built
    for unit in units:
        if unit["name"] in built:
            require(set(unit["deps"]) <= built | set(completed),
                    f"Built unit {unit['name']} has an unbuilt dependency")
    last = plan.get("lastBatch", [])
    require(isinstance(last, list) and all(isinstance(n, str) and n in by_name for n in last)
            and len(last) == len(set(last)), "lastBatch needs unique completed result names")
    circuit = bool(last) and sum(n in built for n in last) * 3 < len(last) * 2
    retry = plan.get("retryUnits", [])
    require(isinstance(retry, list) and all(isinstance(n, str) and n in failed for n in retry)
            and len(retry) == len(set(retry)), "retryUnits must name unique failed units")
    blocked = set()
    while True:
        new = {u["name"] for u in units if u["name"] not in built | failed
               and set(u["deps"]) & (failed | blocked)}
        if new <= blocked:
            break
        blocked.update(new)
    remaining = names - built - failed - blocked
    size = plan.get("batchSize", 4)
    require(type(size) is int and 1 <= size <= 16, "batchSize must be 1..16")
    ready = [u for u in units if u["name"] in remaining | set(retry)
             and set(u["deps"]) <= built | set(completed)]
    return {"nextBatch": [] if circuit else ready[:size], "circuitOpen": circuit,
            "builtUnits": [u for u in units if u["name"] in built],
            "failedUnits": [u for u in units if u["name"] in failed],
            "blockedUnits": [u for u in units if u["name"] in blocked],
            "remainingUnits": [u for u in units if u["name"] in remaining],
            "complete": len(built) == len(units)}


def git(ws, *args):
    return subprocess.run(["git", "-C", str(ws.root), *args], text=True, capture_output=True,
                          check=False, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})


def git_available(ws):
    if not shutil.which("git"):
        return False
    return git(ws, "rev-parse", "--is-inside-work-tree").stdout.strip() == "true"


def secret_paths(ws):
    return [ws.output(f"analysis/{ws.system}/SECRETS.local.md"),
            ws.output(f"analysis/{ws.system}/security_remediation.local.patch")]


def quarantine(ws):
    targets = secret_paths(ws)
    if not git_available(ws):
        identity = hashlib.sha256(str(ws.root).encode()).hexdigest()[:12]
        parent = Path.home() / ".modernize"
        no_links(parent, Path.home())
        folder = no_links(parent / f"{ws.system}-{identity}", Path.home())
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        folder.chmod(0o700)
        return {"inventory": str(folder / targets[0].name), "patch": str(folder / targets[1].name),
                "rawAllowed": False, "storage": "private-non-git"}
    rels = [str(p.relative_to(ws.root)) for p in targets]
    for rel in rels:
        require(not git(ws, "ls-files", "--", rel).stdout.strip(), f"Quarantine path is already tracked: {rel}")
        require(not git(ws, "log", "--all", "-1", "--format=%H", "--", rel).stdout.strip(),
                f"Quarantine path appears in Git history: {rel}")
    ignore = ws.output("analysis/.gitignore")
    existing = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
    missing = [p for p in ("SECRETS.local.md", "*.local.patch") if p not in existing.splitlines()]
    if missing:
        atomic_text(ignore, existing + ("\n" if existing and not existing.endswith("\n") else "")
                    + "\n".join(missing) + "\n")
    for rel in rels:
        require(git(ws, "check-ignore", "-q", "--", rel).returncode == 0, f"Ignore check failed: {rel}")
    ws.analysis.mkdir(parents=True, exist_ok=True)
    for target in targets:
        if target.exists():
            target.chmod(0o600)
    return {"inventory": str(targets[0]), "patch": str(targets[1]),
            "rawAllowed": True, "storage": "gitignored", "newFileMode": "0600"}


def status(ws):
    rows, stale = [], []
    for stage, files in STAGES.items():
        for name in files:
            path = ws.output(f"analysis/{ws.system}/{name}")
            rows.append({"stage": stage, "path": str(path.relative_to(ws.root)), "exists": path.is_file(),
                         "modified": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
                         if path.is_file() else None})
    dependencies = {
        "MODERNIZATION_BRIEF.md": ["ASSESSMENT.md", "topology.json", "BUSINESS_RULES.md", "DELTA_CATALOG.md", "PREFLIGHT.md"],
        "TOPOLOGY.html": ["topology.json"],
    }
    for name, inputs in dependencies.items():
        target = ws.analysis / name
        if target.is_file():
            for item in inputs:
                upstream = ws.analysis / item
                if upstream.is_file() and upstream.stat().st_mtime_ns > target.stat().st_mtime_ns:
                    stale.append({"artifact": name, "newerInput": item})
    notes = []
    for root, pattern in ((ws.transform, "*/TRANSFORMATION_NOTES.md"),
                          (ws.uplift, "UPLIFT_NOTES.md"), (ws.reimagine, "AGENTS.md")):
        if root.is_dir():
            for path in sorted(root.glob(pattern)):
                ws.output(str(path.relative_to(ws.root)))
                if path.is_file():
                    notes.append(str(path.relative_to(ws.root)))
                    rules = ws.analysis / "BUSINESS_RULES.md"
                    if rules.is_file() and rules.stat().st_mtime_ns > path.stat().st_mtime_ns:
                        stale.append({"artifact": str(path.relative_to(ws.root)), "newerInput": "BUSINESS_RULES.md"})
    hygiene = []
    in_git = git_available(ws)
    candidates = secret_paths(ws)
    if ws.analysis.is_dir():
        candidates = sorted(set(candidates) | set(ws.analysis.glob("*.local.patch")))
    for path in candidates:
        ws.output(str(path.relative_to(ws.root)))
        rel = str(path.relative_to(ws.root))
        hygiene.append({"path": rel, "exists": path.is_file(),
                        "ignored": git(ws, "check-ignore", "-q", "--", rel).returncode == 0 if in_git else None,
                        "tracked": bool(git(ws, "ls-files", "--", rel).stdout.strip()) if in_git else None,
                        "inHistory": bool(git(ws, "log", "--all", "-1", "--format=%H", "--", rel).stdout.strip()) if in_git else None})
    stages = ("preflight", "assess", "map", "extract-rules", "brief")
    next_stage = next((s for s in stages if any(r["stage"] == s and not r["exists"] for r in rows)), None)
    if stale:
        next_stage = "map" if any(s["artifact"] == "TOPOLOGY.html" for s in stale) else "brief"
    return {"system": ws.system, "artifacts": rows, "implementationNotes": notes,
            "stale": stale, "secrets": hygiene,
            "nextSkill": f"$codex-modernize:modernize-{next_stage} {ws.system}" if next_stage else None,
            "note": "Presence is not completion or approval. Inspect scope, tests, and user decisions; timestamps are heuristic."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("paths", "topology", "copy", "batch", "quarantine", "status"):
        p = sub.add_parser(name)
        p.add_argument("--workspace", required=True)
        p.add_argument("--system", required=True)
        if name == "batch":
            p.add_argument("--plan", required=True)
    args = parser.parse_args(argv)
    try:
        ws = Workspace(args.workspace, args.system)
        handlers = {"paths": ws.as_dict, "topology": lambda: render_topology(ws),
                    "copy": lambda: copy_source(ws), "quarantine": lambda: quarantine(ws),
                    "status": lambda: status(ws), "batch": lambda: plan_batch(ws, load_json(args.plan))}
        print(json.dumps(handlers[args.command](), indent=2, ensure_ascii=True))
    except (ValidationError, OSError, ValueError, RecursionError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
