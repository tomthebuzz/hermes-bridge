from __future__ import annotations


def move(client, task_id, status, current):
    return client.post(f"/kanban/tasks/{task_id}/transition", json={"status": status, "current_status": current})


def test_auth_required(stub):
    from fastapi.testclient import TestClient
    from app.main import app
    assert TestClient(app).post("/kanban/tasks", json={}).status_code == 401


def test_every_kanban_call_is_pinned_to_the_board(client, stub, create):
    task_id = create()
    client.post(f"/kanban/tasks/{task_id}/comments", json={"text": "hi"})
    assert stub.calls()
    assert all(call[:3] == ["kanban", "--board", "testboard"] for call in stub.calls())


def test_dash_leading_text_survives(client, stub):
    r = client.post("/kanban/tasks", json={"title": "-t", "tenant": "tech", "body": "--not-a-flag", "status": "ready"})
    assert r.status_code == 200, r.text
    import json
    task_id = json.loads(r.json()["detail"])["id"]
    assert client.patch(f"/kanban/tasks/{task_id}", json={"title": "-t2", "body": "-b"}).status_code == 200
    assert client.post(f"/kanban/tasks/{task_id}/comments", json={"text": "-c", "author": "-a"}).status_code == 200
    assert stub.comments(task_id) == [("-a", "-c")]
    assert move(client, task_id, "blocked", "ready").status_code == 200


def test_create_in_each_column(client, stub, create):
    for status, expected in [("triage", "triage"), ("ready", "ready"), ("todo", "ready"), ("blocked", "blocked"),
                             ("running", "ready"), ("review", "review"), ("done", "done"), ("archived", "archived")]:
        assert stub.status(create(status)) == expected, status


def test_attach_passes_author(client, stub, create):
    task_id = create()
    r = client.post(f"/kanban/tasks/{task_id}/attachments", files={"file": ("a.txt", b"x")}, data={"author": "Ana"})
    assert r.status_code == 200, r.text
    assert any(c[3] == "attach" and "--author=Ana" in c for c in stub.calls())


def test_review_loop_and_reject_from_review_column(client, stub, create):
    task_id = create()
    assert client.post(f"/kanban/tasks/{task_id}/publish-for-review", json={"summary": "v1"}).status_code == 200
    assert stub.status(task_id) == "review"
    r = client.post(f"/kanban/tasks/{task_id}/reject", json={"reason": "needs work"})
    assert r.status_code == 200, r.text
    assert stub.status(task_id) == "ready"
    assert ("user", "CHANGES REQUESTED: needs work") in stub.comments(task_id)
    client.post(f"/kanban/tasks/{task_id}/publish-for-review", json={"summary": "v2"})
    assert client.post(f"/kanban/tasks/{task_id}/approve", json={"note": ""}).status_code == 200
    assert stub.status(task_id) == "done"


def test_reject_during_reviewer_run_uses_request_changes(client, stub, create):
    task_id = create("review")
    client.post(f"/kanban/tasks/{task_id}/claim")  # reviewer run claimed from review
    assert client.post(f"/kanban/tasks/{task_id}/reject", json={"reason": "fix"}).status_code == 200
    verbs = [c[3] for c in stub.calls()]
    assert verbs[-1] == "request-changes" and stub.status(task_id) == "ready"


def test_blocked_leaves_via_unblock(client, stub, create):
    task_id = create("blocked")
    assert move(client, task_id, "ready", "blocked").status_code == 200
    assert stub.status(task_id) == "ready"
    assert stub.calls()[-1][3] == "unblock"
    move(client, task_id, "blocked", "ready")
    assert move(client, task_id, "running", "blocked").status_code == 200
    assert stub.status(task_id) == "running"


def test_drag_transitions(client, stub, create):
    task_id = create()
    for target, current in [("running", "ready"), ("review", "running"), ("running", "review"),
                            ("ready", "running"), ("done", "ready"), ("archived", "done")]:
        r = move(client, task_id, target, current)
        assert r.status_code == 200, (target, r.text)
        assert stub.status(task_id) == target


def test_illegal_move_is_explained(client, stub, create):
    task_id = create("done")
    r = move(client, task_id, "todo", "done")
    assert r.status_code == 502 and "Todo" in r.json()["detail"]


def test_edit_requires_a_field(client, stub, create):
    assert client.patch(f"/kanban/tasks/{create()}", json={}).status_code == 422


def test_send_telegram(client, stub):
    r = client.post("/messaging/telegram/send", json={"chat_id": "-100123", "text": "-hello"})
    assert r.status_code == 200, r.text
    assert stub.calls()[-1] == ["send", "--to", "telegram:-100123", "--", "-hello"]


def test_wal_keeper_holds_board_db_read_only(tmp_path, monkeypatch):
    import sqlite3
    from app.config import settings
    from app.core.wal_keeper import WalKeeper
    db = tmp_path / "kanban.db"
    with sqlite3.connect(db) as conn:
        conn.execute("PRAGMA journal_mode=wal")
        conn.execute("CREATE TABLE tasks(id TEXT)")
    monkeypatch.setattr(settings, "kanban_db_path", str(db))
    keeper = WalKeeper()
    keeper.open()
    assert keeper.held
    writer = sqlite3.connect(db)
    writer.execute("INSERT INTO tasks VALUES ('t_1')")
    writer.commit()
    writer.close()  # not the last connection, so the WAL files survive
    assert (tmp_path / "kanban.db-wal").exists() and (tmp_path / "kanban.db-shm").exists()
    import pytest
    with pytest.raises(sqlite3.OperationalError):
        keeper._conn.execute("INSERT INTO tasks VALUES ('t_2')")
    keeper.close()


def test_wal_keeper_never_creates_a_missing_db(tmp_path, monkeypatch):
    from app.config import settings
    from app.core.wal_keeper import WalKeeper
    monkeypatch.setattr(settings, "kanban_db_path", str(tmp_path / "missing.db"))
    keeper = WalKeeper()
    keeper.open()
    assert not keeper.held and not (tmp_path / "missing.db").exists()


def test_reject_from_review_credits_the_reviewer(client, stub, create):
    task_id = create("review")
    r = client.post(f"/kanban/tasks/{task_id}/reject", json={"reason": "fix", "author": "Ana Reviewer"})
    assert r.status_code == 200, r.text
    assert stub.comments(task_id) == [("Ana Reviewer", "CHANGES REQUESTED: fix")]
    assert stub.status(task_id) == "ready"


def test_triage_card_is_specified_then_promoted(client, stub, create):
    task_id = create("triage")
    assert move(client, task_id, "ready", "triage").status_code == 200
    assert [c[3] for c in stub.calls()[-2:]] == ["specify", "promote"]
    assert stub.status(task_id) == "ready"
    other = create("triage")
    assert move(client, other, "todo", "triage").status_code == 200 and stub.status(other) == "ready"
    third = create("triage")
    assert move(client, third, "done", "triage").status_code == 502


def test_assignees_lists_department_profiles(client, stub):
    r = client.get("/kanban/assignees")
    assert r.status_code == 200 and r.json() == ["marketing", "tech"]


def test_new_cards_are_subscribed_to_their_tenant_room(client, stub, tmp_path, monkeypatch):
    import json
    from app.config import settings
    routes = tmp_path / "routes.json"
    routes.write_text(json.dumps({"tech": {"platform": "matrix", "chat_id": "!r:hs", "chat_type": "group",
                                           "notifier_profile": "tech"}}))
    monkeypatch.setattr(settings, "notify_routes_file", str(routes))
    for tenant in ("tech", "sales"):
        assert client.post("/kanban/tasks", json={"title": "T", "tenant": tenant, "status": "ready"}).status_code == 200
    subs = [c for c in stub.calls() if c[3] == "notify-subscribe"]
    assert len(subs) == 1
    assert "--chat-id=!r:hs" in subs[0] and "--notifier-profile=tech" in subs[0]


def test_unreadable_routes_never_block_create(client, stub, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "notify_routes_file", "/nonexistent/routes.json")
    assert client.post("/kanban/tasks", json={"title": "T", "tenant": "tech", "status": "ready"}).status_code == 200


def test_approval_names_the_approver(client, stub, create):
    task_id = create("review")
    assert client.post(f"/kanban/tasks/{task_id}/approve", json={"note": "looks good", "author": "Ana"}).status_code == 200
    assert stub.comments(task_id) == [("Ana", "APPROVED: looks good")]
    assert any(c[3] == "complete" and "--result=Approved by Ana: looks good" in c for c in stub.calls())
    assert stub.status(task_id) == "done"


def test_drag_to_done_names_the_approver(client, stub, create):
    task_id = create("ready")
    r = client.post(f"/kanban/tasks/{task_id}/transition", json={"status": "done", "current_status": "ready", "author": "Ana"})
    assert r.status_code == 200 and stub.comments(task_id) == [("Ana", "APPROVED: Completed from Team Portal")]


def test_generic_send_as_a_profile(client, stub):
    r = client.post("/messaging/send", json={"to": "matrix:!room:hs", "text": "-digest", "profile": "tech"})
    assert r.status_code == 200, r.text
    assert stub.calls()[-1] == ["-p", "tech", "send", "--to", "matrix:!room:hs", "--", "-digest"]
    assert client.post("/messaging/send", json={"to": "email:x@y", "text": "x"}).status_code == 422
    assert client.post("/messaging/send", json={"to": "matrix:!r", "text": "x", "profile": "../etc"}).status_code == 422


def test_logs_never_carry_text_or_tokens():
    from app.core.process_runner import redact
    line = redact(("kanban", "--board", "team", "comment", "--author=Ana Muster", "--", "t_ab12", "secret body jane@x.ch"))
    assert "Ana" not in line and "jane" not in line and "t_ab12" in line and "--author=<10 chars>" in line
    line = redact(("send", "--to", "telegram:-100123", "--", "login https://portal/login/verify?token=abc"))
    assert "token=" not in line and "telegram" not in line


def test_bad_task_ids_never_reach_the_cli(client, stub):
    for bad in ("-h", "--force", "x;rm", "t_" + "a" * 80):
        assert client.post(f"/kanban/tasks/{bad}/claim").status_code in (404, 422)
    assert [c for c in stub.calls() if "claim" in c] == []


def test_a_refused_approval_leaves_no_approved_comment(client, stub, create):
    task_id = create("done")    # Hermes refuses to complete a terminal card
    before = stub.comments(task_id)
    r = client.post(f"/kanban/tasks/{task_id}/approve", json={"note": "again", "author": "Ana"})
    assert r.status_code == 502 and stub.comments(task_id) == before


def test_incomplete_notify_route_does_not_break_create(client, stub, tmp_path, monkeypatch):
    import json
    from app.config import settings
    routes = tmp_path / "routes.json"
    routes.write_text(json.dumps({"tech": {"platform": "matrix"}}))
    monkeypatch.setattr(settings, "notify_routes_file", str(routes))
    assert client.post("/kanban/tasks", json={"title": "T", "tenant": "tech", "status": "ready"}).status_code == 200


def test_assign_separates_options(client, stub, create):
    task_id = create()
    assert client.post(f"/kanban/tasks/{task_id}/assign", json={"assignee": "tech"}).status_code == 200
    assert stub.calls()[-1][3:] == ["assign", "--", task_id, "tech"]


def test_wal_keeper_also_holds_the_team_store(tmp_path, monkeypatch):
    import sqlite3
    from app.config import settings
    from app.core.wal_keeper import WalKeeper
    for name in ("kanban.db", "team.db"):
        with sqlite3.connect(tmp_path / name) as conn:
            conn.execute("PRAGMA journal_mode=wal")
            conn.execute("CREATE TABLE t(id TEXT)")
    monkeypatch.setattr(settings, "kanban_db_path", str(tmp_path / "kanban.db"))
    monkeypatch.setattr(settings, "team_db_path", str(tmp_path / "team.db"))
    keeper = WalKeeper()
    keeper.open()
    assert keeper.held and keeper.extra_held == [str(tmp_path / "team.db")]
    writer = sqlite3.connect(tmp_path / "team.db")
    writer.execute("INSERT INTO t VALUES ('x')")
    writer.commit()
    writer.close()
    assert (tmp_path / "team.db-wal").exists() and (tmp_path / "team.db-shm").exists()
    keeper.close()
    assert keeper.extra_held == []


def test_create_passes_skills_and_creator(client, stub):
    r = client.post("/kanban/tasks", json={"title": "Weekly review", "tenant": "tech", "status": "ready",
                                           "skills": ["team-review"], "created_by": "weekly-review"})
    assert r.status_code == 200, r.text
    call = next(c for c in stub.calls() if "create" in c)
    assert call[call.index("--skill") + 1] == "team-review" and "--created-by=weekly-review" in call
    assert client.post("/kanban/tasks", json={"title": "x", "tenant": "tech", "skills": ["Bad Name"]}).status_code == 422
