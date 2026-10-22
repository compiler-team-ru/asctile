"""Resolve the mirror once and skip an already successful, retained artifact."""
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.parse
import urllib.request
import sys
from datetime import datetime, timezone
from target import get_target, artifact_suffix

SOURCE = "compiler-team-ru/pyasc"


def api(path):
    request = urllib.request.Request("https://api.github.com/" + path, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "pyasc-wheels",
        "Authorization": "Bearer " + os.environ["GH_TOKEN"],
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def recipe_digest(root):
    digest = hashlib.sha256()
    files = [root / ".dockerignore", root / ".github/workflows/wheels.yml", root / "README.md", *sorted((root / "ci").glob("*"))]
    for path in files:
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def valid_sha(value):
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("source_sha must be a full lowercase commit SHA")
    return value


def source_commit():
    branch = api(f"repos/{SOURCE}")["default_branch"]
    supplied = os.environ.get("INPUT_SOURCE_SHA", "")
    ref = valid_sha(supplied) if supplied else branch
    commit = api(f"repos/{SOURCE}/commits/{urllib.parse.quote(ref, safe='')}")
    valid_sha(commit['sha'])
    return branch, commit


def source():
    _, commit = source_commit()
    version = '1.1.1.dev' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        output.write(f"sha={commit['sha']}\nversion={version}\n")


def main():
    root = Path(__file__).resolve().parent.parent
    target = get_target()
    branch, commit = source_commit()
    sha = commit['sha']
    recipe = recipe_digest(root)
    artifact = f"wheel-{sha}-{recipe[:16]}-{artifact_suffix(target)}"
    build = True
    if os.environ.get("INPUT_FORCE", "false") != "true":
        repo = os.environ["GITHUB_REPOSITORY"]
        items = api(f"repos/{repo}/actions/artifacts?" + urllib.parse.urlencode({"name": artifact, "per_page": 100}))
        for item in items["artifacts"]:
            if item["name"] != artifact or item["expired"]:
                continue
            run = api(f"repos/{repo}/actions/runs/{item['workflow_run']['id']}")
            if run["conclusion"] == "success":
                build = False
                break
    manifest = {"source_repository": SOURCE, "default_branch": branch, "source_sha": sha,
                "commit_time": commit["commit"]["committer"]["date"], "recipe_sha256": recipe,
                "artifact": artifact, "build": build, "recipe_commit": os.environ.get("GITHUB_SHA"), "recipe_repository": os.environ.get("GITHUB_REPOSITORY"), "target": target['id']}
    (root / "source.json").write_text(json.dumps(manifest, indent=2) + "\n")
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        for key, value in {"sha": sha, "artifact": artifact, "build": str(build).lower(), "base_image": target['base_image']}.items():
            output.write(f"{key}={value}\n")
    print(json.dumps(manifest))


if __name__ == "__main__":
    source() if sys.argv[1:] == ['source'] else main()
