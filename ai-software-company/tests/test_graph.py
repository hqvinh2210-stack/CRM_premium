from graph.graph import graph


def test_pipeline_create_login_api():
    result = graph.invoke({"task": "Create Login API", "logs": []})

    assert result["task"] == "Create Login API"
    assert result["status"] == "reviewed"
    assert "plan" in result and result["plan"]
    assert "code" in result and len(result["code"]) > 20
    assert "review" in result and "Verdict" in result["review"]
    # memory + planner + coder + reviewer
    assert len(result["logs"]) >= 4
    assert any("memory" in log for log in result["logs"])
