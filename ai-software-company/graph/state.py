from typing import Annotated, TypedDict

import operator


class ProjectState(TypedDict, total=False):
    """Shared state flowing through the LangGraph multi-agent pipeline."""

    # Input
    task: str
    issue_id: str
    run_id: str

    # Agent outputs
    plan: str
    code: str
    review: str
    status: str

    # Memory (shared brain)
    memory_context: str
    memory_hits: list

    # Agent run metadata
    agent_modes: dict

    # Append-only log of node activity
    logs: Annotated[list[str], operator.add]
