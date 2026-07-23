from app.linear import extract_task, handle_linear_webhook, is_issue_create


def test_is_issue_create():
    assert is_issue_create({"type": "Issue", "action": "create"})
    assert not is_issue_create({"type": "Issue", "action": "update"})
    assert not is_issue_create({"type": "Project", "action": "create"})


def test_extract_task():
    task = extract_task(
        {
            "type": "Issue",
            "action": "create",
            "data": {
                "identifier": "JIM-2",
                "title": "Create Login API",
                "description": "Use JWT",
            },
        }
    )
    assert task is not None
    assert "[JIM-2] Create Login API" in task
    assert "Use JWT" in task


def test_handle_issue_create_runs_graph():
    result = handle_linear_webhook(
        {
            "type": "Issue",
            "action": "create",
            "data": {
                "identifier": "JIM-9",
                "title": "Create Login API",
                "description": "email + password",
            },
        }
    )
    assert result["ok"] is True
    assert result["handled"] is True
    assert result["pipeline"]["status"] == "reviewed"
    assert len(result["pipeline"]["logs"]) >= 4
    assert any("memory" in log for log in result["pipeline"]["logs"])


def test_handle_update_ignored():
    result = handle_linear_webhook(
        {
            "type": "Issue",
            "action": "update",
            "data": {"identifier": "JIM-1", "title": "x"},
        }
    )
    assert result["ok"] is True
    assert result["handled"] is False
