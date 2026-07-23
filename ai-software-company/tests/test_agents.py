from agents.coder import coder_agent
from agents.planner import planner_agent
from agents.reviewer import reviewer_agent
from agents.roles import CODER, PLANNER, REVIEWER, list_roles
from graph.graph import graph


def test_roles_registered():
    roles = list_roles()
    ids = {r["id"] for r in roles}
    assert ids == {"planner", "coder", "reviewer"}
    assert PLANNER.name == "Ava"
    assert CODER.name == "Rex"
    assert REVIEWER.name == "Kai"


def test_planner_offline_role_output():
    result = planner_agent.plan("Create Login API")
    assert result.role_id == "planner"
    assert result.mode in {"offline", "llm", "llm_fallback"}
    assert "Goal" in result.content or "goal" in result.content.lower()
    assert len(result.content) > 50


def test_coder_offline_role_output():
    plan = planner_agent.plan("Create Login API").content
    result = coder_agent.code("Create Login API", plan)
    assert result.role_id == "coder"
    assert "def " in result.content or "class " in result.content


def test_reviewer_offline_role_output():
    plan = planner_agent.plan("Create Login API").content
    code = coder_agent.code("Create Login API", plan).content
    result = reviewer_agent.review("Create Login API", plan, code)
    assert result.role_id == "reviewer"
    assert "Verdict" in result.content


def test_graph_uses_agents():
    result = graph.invoke({"task": "Create Login API", "logs": []})
    assert result["status"] == "reviewed"
    assert result["plan"]
    assert result["code"]
    assert result["review"]
    assert "planner" in (result.get("agent_modes") or {})
    assert len(result["logs"]) >= 4
