"""
Push Phase issues to Linear via GraphQL API.

Setup:
  1. Linear → Settings → API → Personal API keys
  2. Add to .env:
       LINEAR_API_KEY=lin_api_...
       LINEAR_TEAM_ID=...   # Team uuid (from Linear URL or API)

Usage:
  uv run python docs/linear/push_linear_issues.py --phase 1
  uv run python docs/linear/push_linear_issues.py --phase 1 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

LINEAR_URL = "https://api.linear.app/graphql"
PHASE_FILES = {
    1: Path(__file__).with_name("issues_phase1.json"),
}


def gql(api_key: str, query: str, variables: dict | None = None) -> dict:
    r = httpx.post(
        LINEAR_URL,
        headers={
            "Authorization": api_key,
            "Content-Type": "application/json",
        },
        json={"query": query, "variables": variables or {}},
        timeout=30.0,
    )
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def ensure_labels(api_key: str, team_id: str, names: list[str]) -> dict[str, str]:
    """Return map label_name -> label_id; create missing labels."""
    q = """
    query($teamId: String!) {
      team(id: $teamId) {
        labels { nodes { id name } }
      }
    }
    """
    data = gql(api_key, q, {"teamId": team_id})
    existing = {n["name"]: n["id"] for n in data["team"]["labels"]["nodes"]}
    create_m = """
    mutation($id: String!, $name: String!) {
      issueLabelCreate(input: { teamId: $id, name: $name }) {
        success
        issueLabel { id name }
      }
    }
    """
    for name in names:
        if name in existing:
            continue
        try:
            created = gql(api_key, create_m, {"id": team_id, "name": name})
            lab = created["issueLabelCreate"]["issueLabel"]
            existing[lab["name"]] = lab["id"]
            print(f"  + label {name}")
        except Exception as exc:
            print(f"  ! label {name}: {exc}")
    return existing


def create_issue(
    api_key: str,
    team_id: str,
    *,
    title: str,
    description: str,
    priority: int,
    label_ids: list[str],
) -> str:
    m = """
    mutation($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue { id identifier title url }
      }
    }
    """
    payload = {
        "teamId": team_id,
        "title": title,
        "description": description,
        "priority": priority,
    }
    if label_ids:
        payload["labelIds"] = label_ids
    data = gql(api_key, m, {"input": payload})
    issue = data["issueCreate"]["issue"]
    return f"{issue['identifier']} {issue['title']} → {issue.get('url', '')}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=int, default=1, choices=sorted(PHASE_FILES))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Max issues (0=all)")
    args = parser.parse_args()

    api_key = os.getenv("LINEAR_API_KEY")
    team_id = os.getenv("LINEAR_TEAM_ID")
    path = PHASE_FILES[args.phase]
    issues = json.loads(path.read_text(encoding="utf-8"))
    if args.limit:
        issues = issues[: args.limit]

    print(f"Phase {args.phase}: {len(issues)} issues from {path.name}")

    if args.dry_run:
        for i, issue in enumerate(issues, 1):
            print(f"{i:02d}. {issue['title']}")
        print("Dry-run only. Set LINEAR_API_KEY + LINEAR_TEAM_ID to push.")
        return 0

    if not api_key or not team_id:
        print(
            "Missing LINEAR_API_KEY or LINEAR_TEAM_ID in .env\n"
            "Create key: Linear → Settings → API → Personal API keys\n"
            "Team id: open team in Linear, or query teams { nodes { id name } }",
            file=sys.stderr,
        )
        return 1

    all_labels = sorted({lb for it in issues for lb in it.get("labels", [])})
    print("Ensuring labels...")
    label_map = ensure_labels(api_key, team_id, all_labels)

    for issue in issues:
        label_ids = [label_map[n] for n in issue.get("labels", []) if n in label_map]
        try:
            info = create_issue(
                api_key,
                team_id,
                title=issue["title"],
                description=issue.get("description", ""),
                priority=int(issue.get("priority", 3)),
                label_ids=label_ids,
            )
            print("Created:", info)
        except Exception as exc:
            print("FAILED:", issue["title"], exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
