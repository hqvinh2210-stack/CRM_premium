"""Create + mark Done remaining Phase 3/4 issues after v0.7 build."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
LINEAR = "https://api.linear.app/graphql"

ITEMS = [
    (
        "[P3-M4-T4] Wire LangGraph agents to POS events",
        "POST /api/v1/ai/event + outbox AGENT_ON_ORDER + Celery task run_pos_agent_event + memory note.",
    ),
    (
        "[P4-M1-T1] Offline conflict resolution UI",
        "syncOfflineOrders returns conflicts; PosApp banner + manual_resolve list; server_price_wins.",
    ),
    (
        "[P4-M4-T1] Sentry optional + CI",
        "SENTRY_DSN init in FastAPI lifespan; existing GitHub Actions pipeline.",
    ),
    (
        "[P4-M5-T1] SoftPOS camera barcode assist",
        "ProductGrid camera toggle (getUserMedia environment) + PWA manifest.",
    ),
    (
        "[P4-M6-T1] Export PDF reports",
        "GET /api/v1/reports/export.pdf minimal PDF + EodPanel Xuất PDF button.",
    ),
]


def gql(key: str, q: str, v: dict | None = None) -> dict:
    r = httpx.post(
        LINEAR,
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
        print("Missing LINEAR_API_KEY / LINEAR_TEAM_ID", file=sys.stderr)
        return 1

    data = gql(
        key,
        """
        query($id: String!) {
          team(id: $id) {
            states { nodes { id name type } }
            issues(first: 100) { nodes { id identifier title state { type name } } }
          }
        }
        """,
        {"id": team},
    )
    done = next(s for s in data["team"]["states"]["nodes"] if s["type"] == "completed")
    by_title = {i["title"]: i for i in data["team"]["issues"]["nodes"]}

    for title, note in ITEMS:
        issue = by_title.get(title)
        if not issue:
            created = gql(
                key,
                """
                mutation($input: IssueCreateInput!) {
                  issueCreate(input: $input) {
                    success
                    issue { id identifier title }
                  }
                }
                """,
                {
                    "input": {
                        "teamId": team,
                        "title": title,
                        "description": note,
                        "priority": 3,
                    }
                },
            )
            issue = created["issueCreate"]["issue"]
            print("Created", issue["identifier"], title)
        else:
            print("Exists", issue.get("identifier"), title)

        if issue.get("state", {}).get("type") == "completed":
            print("  already Done")
            continue

        gql(
            key,
            """
            mutation($id: String!, $stateId: String!) {
              issueUpdate(id: $id, input: { stateId: $stateId }) {
                success
              }
            }
            """,
            {"id": issue["id"], "stateId": done["id"]},
        )
        # comment
        try:
            gql(
                key,
                """
                mutation($id: String!, $body: String!) {
                  commentCreate(input: { issueId: $id, body: $body }) { success }
                }
                """,
                {"id": issue["id"], "body": f"✅ Implemented in v0.7.0\n\n{note}"},
            )
        except Exception as exc:  # noqa: BLE001
            print("  comment skip:", exc)
        print("  → Done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
