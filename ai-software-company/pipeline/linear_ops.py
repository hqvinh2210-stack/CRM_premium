"""Create Linear issues so agents (webhook → LangGraph) can continue work."""

from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

LINEAR_URL = "https://api.linear.app/graphql"


def _client_headers() -> dict[str, str] | None:
    key = os.getenv("LINEAR_API_KEY")
    if not key:
        return None
    return {"Authorization": key, "Content-Type": "application/json"}


def gql(query: str, variables: dict | None = None) -> dict[str, Any]:
    headers = _client_headers()
    if not headers:
        raise RuntimeError("LINEAR_API_KEY not set")
    r = httpx.post(
        LINEAR_URL,
        headers=headers,
        json={"query": query, "variables": variables or {}},
        timeout=30.0,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        raise RuntimeError(str(data["errors"]))
    return data["data"]


def create_agent_task(
    *,
    title: str,
    description: str,
    labels: list[str] | None = None,
    priority: int = 2,
) -> dict[str, Any]:
    """
    Create a Linear issue. Webhook Issue Created → orchestrator → Ava/Rex/Kai.

    priority: 0=none 1=urgent 2=high 3=medium 4=low
    """
    team_id = os.getenv("LINEAR_TEAM_ID")
    if not team_id:
        raise RuntimeError("LINEAR_TEAM_ID not set")

    label_ids: list[str] = []
    wanted = labels or ["type:bug", "pipeline:auto", "area:backend"]
    try:
        team = gql(
            """
            query($id: String!) {
              team(id: $id) { labels { nodes { id name } } }
            }
            """,
            {"id": team_id},
        )
        existing = {n["name"]: n["id"] for n in team["team"]["labels"]["nodes"]}
        for name in wanted:
            if name in existing:
                label_ids.append(existing[name])
            else:
                created = gql(
                    """
                    mutation($teamId: String!, $name: String!) {
                      issueLabelCreate(input: { teamId: $teamId, name: $name }) {
                        issueLabel { id name }
                      }
                    }
                    """,
                    {"teamId": team_id, "name": name},
                )
                lab = created["issueLabelCreate"]["issueLabel"]
                label_ids.append(lab["id"])
    except Exception as exc:
        print(f"[linear_ops] label ensure skipped: {exc}")

    data = gql(
        """
        mutation($input: IssueCreateInput!) {
          issueCreate(input: $input) {
            success
            issue { id identifier title url }
          }
        }
        """,
        {
            "input": {
                "teamId": team_id,
                "title": title[:200],
                "description": description[:50000],
                "priority": priority,
                **({"labelIds": label_ids} if label_ids else {}),
            }
        },
    )
    issue = data["issueCreate"]["issue"]
    print(f"[linear_ops] Created {issue['identifier']}: {issue.get('url')}")
    return issue


def report_pipeline_failure(
    *,
    stage: str,
    summary: str,
    detail: str,
    source: str = "pipeline",
) -> dict[str, Any] | None:
    """Open Linear task for failed stage so agents can fix."""
    title = f"[AUTO/{stage.upper()}] {summary}"
    body = f"""## Pipeline failure → Agent handoff

**Stage:** `{stage}`  
**Source:** `{source}`  

### Summary
{summary}

### Detail
```
{detail[:8000]}
```

## Agent instructions
1. **Ava**: root-cause plan + files to touch  
2. **Rex**: implement fix + tests  
3. **Kai**: review security/money/stock regressions  
4. Re-run: `uv run python -m pipeline run --from test`

## Acceptance
- [ ] Root cause fixed
- [ ] Tests green
- [ ] Health check OK
"""
    try:
        return create_agent_task(
            title=title,
            description=body,
            labels=["type:bug", "pipeline:auto", f"stage:{stage}"],
            priority=1 if stage in {"deploy", "production"} else 2,
        )
    except Exception as exc:
        print(f"[linear_ops] Failed to create Linear issue: {exc}")
        return None
