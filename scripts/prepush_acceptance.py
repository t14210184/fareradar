from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCANNED_SUFFIXES = {".py", ".ts", ".js", ".mjs", ".cjs", ".yml", ".yaml", ".json", ".jsonc"}
PLACEHOLDER_TOKEN = "PLACE" + "HOLDER"
PLACEHOLDER_RE = re.compile(rf"(?<![A-Za-z0-9_]){PLACEHOLDER_TOKEN}(?![A-Za-z0-9_])")
CHECKS = (
    ("npm", "run", "check:ts"),
    ("npm", "run", "check:wrangler"),
    ("pytest", "-q"),
    ("python3", "scripts/validate_invariants.py"),
    ("git", "diff", "--check", "HEAD"),
)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def require_clean_worktree() -> None:
    state = git("status", "--porcelain", "--untracked-files=all")
    if state:
        raise RuntimeError("PREPUSH_DIRTY_WORKTREE")


def contains_forbidden_placeholder(text: str) -> bool:
    return PLACEHOLDER_RE.search(text) is not None


def placeholder_violations() -> list[str]:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    violations: list[str] = []
    for item in raw.decode("utf-8").split("\0"):
        if not item:
            continue
        path = ROOT / item
        if path.suffix.lower() not in SCANNED_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if contains_forbidden_placeholder(text):
            violations.append(item)
    return violations


def run_checks() -> None:
    for command in CHECKS:
        subprocess.run(list(command), cwd=ROOT, check=True)


def main() -> int:
    try:
        require_clean_worktree()
        violations = placeholder_violations()
        if violations:
            raise RuntimeError("PREPUSH_FORBIDDEN_PLACEHOLDER:" + ",".join(sorted(violations)))
        run_checks()
        require_clean_worktree()
        print("PREPUSH_ACCEPTANCE_PASS")
        return 0
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
