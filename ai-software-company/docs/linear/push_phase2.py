"""Push Phase 2 issues to Linear for next iteration."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
LINEAR_URL = "https://api.linear.app/graphql"
ISSUES = json.loads((Path(__file__).parent / "ISSUES_PHASE2_4.json").read_text(encoding="utf-8"))


def gql(key: str, q: str, v: dict | None = None) -> dict:
    r = httpx.post(
        LINEAR_URL,
        headers={"Authorization": key, "Content-Type": "application/json"},
        json={"query": q, "variables": v or {}},
        timeout=45,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data["data"]


def main() -> int:
    key = os.getenv("LINEAR_API_KEY")
    team = os.getenv("LINEAR_TEAM_ID")
    if not key or not team:
        print("Missing LINEAR credentials", file=sys.stderr)
        return 1

    # existing titles to skip duplicates
    existing = gql(
        key,
        """
        query($id: String!) {
          team(id: $id) {
            issues(first: 100) { nodes { title } }
          }
        }
        """,
        {"id": team},
    )
    titles = {i["title"] for i in existing["team"]["issues"]["nodes"]}

    create = """
    mutation($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue { identifier title url }
      }
    }
    """
    # Phase 2 first
    for issue in ISSUES["phase2"]:
        if issue["title"] in titles:
            print("SKIP", issue["title"][:60])
            continue
        desc = f"""## Goal
Phase 2 task from POS+CRM plan.

## Title
{issue['title']}

## Labels
{', '.join(issue.get('labels', []))}

## Agent handoff
Ava plan → Rex implement → Kai review.
Re-run: `uv run python -m pipeline run --from review`
"""
        data = gql(
            key,
            create,
            {
                "input": {
                    "teamId": team,
                    "title": issue["title"],
                    "description": desc,
                    "priority": int(issue.get("priority", 3)),
                }
            },
        )
        iss = data["issueCreate"]["issue"]
        print("Created", iss["identifier"], iss.get("url"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
