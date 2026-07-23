from pathlib import Path

from memory.local_store import LocalMemoryStore
from memory.service import MemoryService


def test_local_store_add_search(tmp_path: Path):
    store = LocalMemoryStore(tmp_path / "m.jsonl")
    store.add(
        "Team prefers FastAPI and JWT for auth",
        user_id="crm_company",
        agent_id="planner",
    )
    store.add(
        "Use Pydantic models for request validation",
        user_id="crm_company",
        agent_id="coder",
    )
    hits = store.search("FastAPI JWT login", user_id="crm_company", top_k=3)
    assert hits
    assert any("FastAPI" in h["memory"] for h in hits)


def test_memory_service_remember_recall(tmp_path: Path, monkeypatch):
    store = LocalMemoryStore(tmp_path / "m.jsonl")
    svc = MemoryService(
        user_id="crm_company",
        local=store,
        mem0=None,
        mem0_enabled=False,
    )
    svc.remember("Prefer REST over GraphQL for this CRM", agent_id="company")
    hits = svc.recall("REST CRM API")
    assert hits
    ctx = svc.format_context(hits)
    assert "Shared company memory" in ctx
    assert "REST" in ctx


def test_graph_memory_pipeline():
    from graph.graph import graph

    # seed via service used by graph
    from memory.service import get_memory_service

    mem = get_memory_service()
    mem.remember(
        "Company standard: all auth APIs must use JWT bearer tokens",
        agent_id="company",
        metadata={"kind": "standard"},
    )

    r1 = graph.invoke({"task": "Create Login API", "logs": []})
    assert r1["status"] == "reviewed"
    assert r1.get("run_id")
    assert isinstance(r1.get("memory_hits"), list)
    # second run should see memories from first
    r2 = graph.invoke({"task": "Create Login API with refresh token", "logs": []})
    assert r2["status"] == "reviewed"
    # logs include memory node
    assert any("memory" in log for log in r2["logs"])
