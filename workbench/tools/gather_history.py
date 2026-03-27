#!/usr/bin/env python3
"""Gather and combine project history from Git, GitHub, Claude Code, and Conductor.

Produces a unified CSV timeline at workbench/data/project_history.csv with columns:
  timestamp, source, category, summary, detail, session_id, branch, url

Sources:
  - Git commits (local repo)
  - GitHub PRs and Issues (via gh CLI)
  - Claude Code sessions (~/.claude/projects/-Users-s0shaheen-Dev-attic/)
  - Claude Code command history (~/.claude/history.jsonl)
  - Conductor workspace sessions (~/.claude/projects/-Users-s0shaheen-conductor-workspaces-attic-*/)
"""

import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CLAUDE_DIR = Path.home() / ".claude"
ATTIC_SESSIONS = CLAUDE_DIR / "projects" / "-Users-s0shaheen-Dev-attic"
CONDUCTOR_BASE = CLAUDE_DIR / "projects"
HISTORY_JSONL = CLAUDE_DIR / "history.jsonl"
OUTPUT_CSV = REPO_ROOT / "workbench" / "data" / "project_history.csv"


def run(cmd: list[str], cwd: Path | None = None) -> str:
    """Run a shell command and return stdout, or empty string on failure."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=cwd)
        return r.stdout.strip()
    except Exception:
        return ""


# ── Git Commits ────────────────────────────────────────────────────────────────

def gather_git_commits() -> list[dict]:
    """Get all commits from the local repo."""
    rows = []
    # format: iso-date ||| subject ||| hash ||| branch-decorations
    raw = run(
        ["git", "log", "--all", "--format=%aI|||%s|||%H|||%D", "--date=iso-strict"],
        cwd=REPO_ROOT,
    )
    if not raw:
        return rows
    for line in raw.splitlines():
        parts = line.split("|||")
        if len(parts) < 3:
            continue
        ts, subject, sha = parts[0].strip(), parts[1].strip(), parts[2].strip()
        branch = parts[3].strip() if len(parts) > 3 else ""
        rows.append({
            "timestamp": ts,
            "source": "git",
            "category": "commit",
            "summary": subject,
            "detail": sha[:10],
            "session_id": "",
            "branch": branch,
            "url": "",
        })
    print(f"  git commits: {len(rows)}")
    return rows


# ── GitHub PRs ─────────────────────────────────────────────────────────────────

def gather_github_prs() -> list[dict]:
    rows = []
    raw = run([
        "gh", "pr", "list", "--state", "all", "--limit", "200",
        "--json", "number,title,state,createdAt,mergedAt,closedAt,headRefName,url,body",
    ])
    if not raw:
        return rows
    for pr in json.loads(raw):
        branch = pr.get("headRefName", "")
        # Skip automated PRs (dependabot, renovate, etc.)
        if branch.startswith(("dependabot/", "renovate/")) or pr.get("title", "").startswith(("deps(", "chore(deps)")):
            continue
        ts = pr.get("mergedAt") or pr.get("closedAt") or pr.get("createdAt", "")
        state = pr.get("state", "").lower()
        body_preview = (pr.get("body") or "").replace("\n", " ")
        rows.append({
            "timestamp": ts,
            "source": "github",
            "category": f"pr-{state}",
            "summary": f"#{pr['number']} {pr['title']}",
            "detail": body_preview,
            "session_id": "",
            "branch": pr.get("headRefName", ""),
            "url": pr.get("url", ""),
        })
    print(f"  github PRs: {len(rows)}")
    return rows


# ── GitHub Issues ──────────────────────────────────────────────────────────────

def gather_github_issues() -> list[dict]:
    rows = []
    raw = run([
        "gh", "issue", "list", "--state", "all", "--limit", "300",
        "--json", "number,title,state,createdAt,closedAt,labels,url",
    ])
    if not raw:
        return rows
    for issue in json.loads(raw):
        ts = issue.get("closedAt") or issue.get("createdAt", "")
        state = issue.get("state", "").lower()
        labels = ", ".join(l["name"] for l in issue.get("labels", []))
        rows.append({
            "timestamp": ts,
            "source": "github",
            "category": f"issue-{state}",
            "summary": f"#{issue['number']} {issue['title']}",
            "detail": labels,
            "session_id": "",
            "branch": "",
            "url": issue.get("url", ""),
        })
    print(f"  github issues: {len(rows)}")
    return rows


# ── Claude Code Command History ────────────────────────────────────────────────

def gather_command_history() -> list[dict]:
    """Parse ~/.claude/history.jsonl for slash-commands and prompts."""
    rows = []
    if not HISTORY_JSONL.exists():
        return rows
    for line in HISTORY_JSONL.read_text().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Only include attic project entries
        project = entry.get("project", "")
        if "attic" not in project:
            continue
        ts_ms = entry.get("timestamp")
        if ts_ms:
            ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
        else:
            ts = ""
        display = entry.get("display", "").strip()
        rows.append({
            "timestamp": ts,
            "source": "claude-code",
            "category": "command",
            "summary": display[:200],
            "detail": "",
            "session_id": entry.get("sessionId", ""),
            "branch": "",
            "url": "",
        })
    print(f"  claude-code commands: {len(rows)}")
    return rows


# ── Claude Code & Conductor Sessions ──────────────────────────────────────────

def _parse_session_dir(session_dir: Path, source_label: str) -> list[dict]:
    """Parse all JSONL session files in a directory.

    Extracts: session start/end, user messages (first line), branch, model.
    """
    rows = []
    jsonl_files = sorted(session_dir.glob("*.jsonl"))
    for f in jsonl_files:
        session_id = f.stem
        messages: list[dict] = []
        session_start = None
        session_branch = ""
        session_model = ""

        for line in f.read_text(errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Track session metadata
            if entry.get("type") == "user":
                ts = entry.get("timestamp", "")
                branch = entry.get("gitBranch", "")
                if branch:
                    session_branch = branch
                if not session_start and ts:
                    session_start = ts

                # Extract user message text
                msg = entry.get("message", {})
                content = msg.get("content", [])
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        t = part["text"]
                        # Skip IDE context tags
                        if t.startswith("<ide_") or t.startswith("<system-reminder"):
                            continue
                        text_parts.append(t)
                    elif isinstance(part, str):
                        text_parts.append(part)
                text = " ".join(text_parts).strip()
                if text:
                    messages.append({"timestamp": ts, "text": text})

            # Track model
            if entry.get("type") == "message" and entry.get("role") == "assistant":
                m = entry.get("model", "")
                if m:
                    session_model = m

        if not messages:
            continue

        # Emit session-start event
        first_msg = messages[0]["text"][:300].replace("\n", " ")
        rows.append({
            "timestamp": session_start or "",
            "source": source_label,
            "category": "session-start",
            "summary": first_msg,
            "detail": f"messages={len(messages)} model={session_model}",
            "session_id": session_id,
            "branch": session_branch,
            "url": "",
        })

        # Emit each user message as a row
        for m in messages:
            text = m["text"][:300].replace("\n", " ")
            rows.append({
                "timestamp": m["timestamp"],
                "source": source_label,
                "category": "user-message",
                "summary": text,
                "detail": "",
                "session_id": session_id,
                "branch": session_branch,
                "url": "",
            })

    return rows


def gather_claude_sessions() -> list[dict]:
    rows = []
    if ATTIC_SESSIONS.exists():
        rows = _parse_session_dir(ATTIC_SESSIONS, "claude-code")
    print(f"  claude-code sessions: {len(rows)}")
    return rows


def gather_conductor_sessions() -> list[dict]:
    all_rows = []
    if not CONDUCTOR_BASE.exists():
        return all_rows
    for d in sorted(CONDUCTOR_BASE.iterdir()):
        if not d.is_dir():
            continue
        if "conductor-workspaces-attic" not in d.name:
            continue
        # Extract city name
        city = d.name.split("attic-", 1)[-1] if "attic-" in d.name else d.name
        rows = _parse_session_dir(d, f"conductor/{city}")
        all_rows.extend(rows)
    print(f"  conductor sessions: {len(all_rows)}")
    return all_rows


# ── Main ───────────────────────────────────────────────────────────────────────

FIELDS = ["timestamp", "source", "category", "summary", "detail", "session_id", "branch", "url"]


def main():
    print("Gathering project history...")
    all_rows: list[dict] = []

    all_rows.extend(gather_git_commits())
    all_rows.extend(gather_github_prs())
    all_rows.extend(gather_github_issues())
    all_rows.extend(gather_command_history())
    all_rows.extend(gather_claude_sessions())
    all_rows.extend(gather_conductor_sessions())

    # Filter to after 2026-02-12 and sort descending
    cutoff = "2026-02-12"
    all_rows = [r for r in all_rows if r.get("timestamp", "") >= cutoff]
    all_rows.sort(key=lambda r: r.get("timestamp", ""), reverse=True)

    # Write CSV
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nDone! {len(all_rows)} rows → {OUTPUT_CSV}")

    # Quick stats
    sources = {}
    for r in all_rows:
        src = r["source"]
        sources[src] = sources.get(src, 0) + 1
    print("\nBreakdown:")
    for src, count in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"  {src}: {count}")


if __name__ == "__main__":
    main()
