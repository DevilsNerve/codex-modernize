#!/usr/bin/env python3
"""Validate the distributable package and run the standard-library test suite."""
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/codex-modernize"
SKILLS = {"preflight", "assess", "map", "extract-rules", "brief", "transform",
          "reimagine", "uplift", "harden", "status"}


def validate():
    manifest = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())
    portable = json.loads((PLUGIN / "plugin.json").read_text())
    market = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
    assert manifest["name"] == portable["name"] == PLUGIN.name
    assert manifest["version"] == portable["version"], "Manifest versions disagree"
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?", manifest["version"])
    assert portable["extensions"]["com.openai"]["interface"] == manifest["interface"]
    assert manifest["skills"] == "./skills/"
    entry, = market["plugins"]
    assert entry["name"] == PLUGIN.name
    assert (ROOT / entry["source"]["path"]).resolve() == PLUGIN
    assert entry["policy"] == {"installation":"AVAILABLE", "authentication":"ON_INSTALL"}
    assert entry["category"]
    actual = {p.name.removeprefix("modernize-") for p in (PLUGIN / "skills").iterdir() if p.is_dir()}
    assert actual == SKILLS, f"Skill inventory mismatch: {actual}"
    for skill in (PLUGIN / "skills").iterdir():
        if not skill.is_dir():
            continue
        content = (skill / "SKILL.md").read_text()
        _, front, body = content.split("---", 2)
        assert f"name: {skill.name}\n" in front
        description = re.search(r"^description: (.+)$", front, re.M).group(1)
        assert 20 < len(json.loads(description)) < 1024
        assert "../../references/runtime.md" in body
        assert "$codex-modernize:" + skill.name in body
        assert (skill / "agents/openai.yaml").is_file()
    for path in PLUGIN.rglob("*"):
        assert not path.is_symlink(), f"Package contains symlink: {path}"
        if path.suffix not in (".md", ".json", ".yaml", ".html") or not path.is_file():
            continue
        text = path.read_text()
        assert "[TODO:" not in text, f"Unfinished scaffold in {path}"
        if path.suffix == ".md":
            for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
                if "://" in link or link.startswith("#"):
                    continue
                target = (path.parent / link.split("#")[0]).resolve()
                assert target == PLUGIN or PLUGIN in target.parents, f"Reference leaves plugin: {path}: {link}"
                assert target.exists(), f"Broken reference: {path}: {link}"
            if path.name != "NOTICE.md":
                for unsupported in ("${CLAUDE_PLUGIN_ROOT}", "$ARGUMENTS", "Workflow({", "CLAUDE.md", "tools: Read"):
                    assert unsupported not in text, f"Unported runtime token {unsupported} in {path}"
    for filename in ("LICENSE.md", "NOTICE.md", "THIRD_PARTY_LICENSES/Apache-2.0.txt", "THIRD_PARTY_LICENSES/D3-ISC.txt"):
        assert (PLUGIN / filename).is_file(), f"Missing license: {filename}"
    assert (ROOT / "LICENSE.md").read_bytes() == (PLUGIN / "LICENSE.md").read_bytes()
    viewer = (PLUGIN / "assets/topology-viewer.html").read_text()
    assert viewer.count("/*__TOPOLOGY_DATA__*/ null") == 1
    assert not re.search(r"<script\s+[^>]*src=", viewer, re.I)
    assert "Permission to use, copy, modify" in viewer
    print(f"Package valid: {manifest['name']} {manifest['version']}; {len(SKILLS)} native skills.", flush=True)


if __name__ == "__main__":
    validate()
    sys.exit(subprocess.call([sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"], cwd=ROOT))
