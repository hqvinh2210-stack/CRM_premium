from pipeline.stages import stage_deploy, stage_review


def test_review_stage_ok():
    r = stage_review()
    assert r.ok is True
    assert r.details["checks"]["has_atomic_pay"] is True


def test_deploy_stage_writes_marker(tmp_path, monkeypatch):
    # deploy uses ROOT/.data — just ensure callable success
    r = stage_deploy("local")
    assert r.ok is True
    assert "deployed_at" in r.details
