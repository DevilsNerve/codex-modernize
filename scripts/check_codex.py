#!/usr/bin/env python3
"""Check installed skills through the real Codex app-server protocol (no model call).

Install the plugin first using the README. This does not change Codex settings.
"""
import argparse
import json
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time

EXPECTED = {"modernize-" + stage for stage in ("preflight", "assess", "map", "extract-rules",
            "brief", "transform", "reimagine", "uplift", "harden", "status")}


def check(workspace):
    with tempfile.TemporaryFile(mode="w+") as log:
        process = subprocess.Popen(["codex", "app-server", "--stdio"], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=log, text=True, bufsize=1,
                                   cwd=workspace)
        messages = queue.Queue()

        def reader():
            for line in process.stdout:
                try:
                    messages.put(json.loads(line))
                except json.JSONDecodeError:
                    continue
            messages.put({"error": "app-server exited"})

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()

        def request(identifier, method, params):
            process.stdin.write(json.dumps({"id":identifier,"method":method,"params":params}) + "\n")
            process.stdin.flush()
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                item = messages.get(timeout=max(0.01, deadline - time.monotonic()))
                if item.get("id") == identifier or item.get("error"):
                    if "error" in item:
                        raise RuntimeError(str(item["error"]))
                    return item["result"]
            raise TimeoutError(method)

        try:
            request(1, "initialize", {"clientInfo":{"name":"codex-modernize-check", "version":"1.0.0"},
                                      "capabilities":{"experimentalApi":True}})
            process.stdin.write('{"method":"initialized","params":{}}\n')
            process.stdin.flush()
            response = request(2, "skills/list", {"cwds":[str(workspace)],"forceReload":True})
            found = []
            for group in response["data"]:
                errors = [e for e in group.get("errors", []) if "codex-modernize" in str(e)]
                assert not errors, errors
                found.extend(s for s in group["skills"] if s.get("pluginId") == "codex-modernize@codex-modernize")
            actual = {s["name"].removeprefix("codex-modernize:") for s in found}
            assert actual == EXPECTED, f"Expected ten installed skills; found {sorted(actual)}"
            for skill in found:
                assert skill["enabled"], f"Disabled skill: {skill['name']}"
                path = Path(skill["path"])
                assert path.is_file(), path
                assert (path.parent / "../../references/runtime.md").resolve().is_file()
            source = Path(__file__).resolve().parents[1] / "plugins/codex-modernize"
            installed = Path(found[0]["path"]).parents[2]
            compared = 0
            for original in source.rglob("*"):
                if not original.is_file() or "__pycache__" in original.parts:
                    continue
                copy = installed / original.relative_to(source)
                assert copy.is_file(), f"Missing bundled file: {original.relative_to(source)}"
                assert copy.read_bytes() == original.read_bytes(), f"Stale installed file: {original.relative_to(source)}"
                compared += 1
            print(json.dumps({"loaded":len(found), "enabled":True,
                              "installedFilesMatchSource":compared,
                              "skills":sorted(s["name"] for s in found)}, indent=2))
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=5)
            thread.join(timeout=1)
            process.stdin.close(); process.stdout.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    check(args.workspace.resolve())
