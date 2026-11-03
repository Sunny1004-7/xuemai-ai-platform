"""Negative contracts: authorization, associations, private files and AI budgets.

All databases/uploads are temporary; AI transport is blocked unless a test
explicitly supplies httpx.MockTransport. No real provider request is possible.
"""
import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app import ai
from backend.app.ai import AIConfig, AIError, AIService, RateLimiter
from backend.app.db import get_db
from backend.app.main import app


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "security.db"))
    monkeypatch.setenv("AI_MODE", "mock")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "offline-test-placeholder")
    monkeypatch.setattr(ai, "limiter", RateLimiter())
    monkeypatch.setattr(ai, "log_usage", lambda *args, **kwargs: None)
    original = httpx.AsyncClient
    def offline_client(*args, **kwargs):
        assert kwargs.get("transport") is not None, "安全测试禁止访问真实网络"
        return original(*args, **kwargs)
    monkeypatch.setattr(ai.httpx, "AsyncClient", offline_client)


@pytest.fixture
def client():
    with TestClient(app) as api:
        yield api


def login(client, username="student1"):
    response = client.post("/api/auth/login", json={"username": username, "password": "Xuemai123!"})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["token"]}


def test_expired_session_rejected_before_ai_work(client, monkeypatch):
    headers = login(client)
    with get_db() as db:
        db.execute("UPDATE sessions SET expires_at=0")
    def forbidden(*args, **kwargs):
        raise AssertionError("失效会话不得创建AI服务")
    monkeypatch.setattr("backend.app.ai_routes.AIService", forbidden)
    response = client.post("/api/ai/chat", headers=headers, json={"course_id": 1, "message": "测试"})
    assert response.status_code == 401 and "event: meta" not in response.text


@pytest.mark.parametrize("method,path,payload", [
    ("POST", "/api/ai/generate", {"course_id": 1, "kind": "lesson"}),
    ("POST", "/api/questions", {"course_id": 1, "knowledge_id": 2, "type": "fill", "title": "越权", "answer": "答案"}),
    ("PATCH", "/api/questions/1", {"course_id": 1, "knowledge_id": 2, "type": "fill", "title": "越权", "answer": "答案"}),
    ("DELETE", "/api/questions/1", None),
    ("DELETE", "/api/knowledge/2", None),
    ("POST", "/api/classroom", {"course_id": 1, "title": "越权", "prompt": "测试"}),
    ("POST", "/api/assignments", {"course_id": 1, "title": "越权", "question_ids": [1]}),
])
def test_student_cannot_mutate_teacher_objects(client, method, path, payload):
    response = client.request(method, path, headers=login(client), json=payload)
    assert response.status_code == 403


@pytest.mark.parametrize("path,payload", [
    ("/api/notes", {"course_id": 1, "resource_id": 9, "content": "跨课程引用"}),
    ("/api/notes", {"course_id": 1, "knowledge_id": 9, "content": "跨课程知识"}),
    ("/api/events", {"course_id": 1, "kind": "video_progress", "payload": {"resource_id": 9, "current_time": 2}}),
    ("/api/events", {"course_id": 1, "knowledge_id": 9, "kind": "experiment"}),
])
def test_cross_course_association_rejected_without_partial_write(client, path, payload):
    headers = login(client)
    with get_db() as db:
        before = db.execute("SELECT COUNT(*) FROM notes").fetchone()[0], db.execute("SELECT COUNT(*) FROM learning_events").fetchone()[0]
    assert client.post(path, headers=headers, json=payload).status_code == 422
    with get_db() as db:
        after = db.execute("SELECT COUNT(*) FROM notes").fetchone()[0], db.execute("SELECT COUNT(*) FROM learning_events").fetchone()[0]
    assert before == after


def test_resource_upload_role_type_and_encoding_limits(client):
    student = login(client)
    teacher = login(client, "teacher")
    data = {"course_id": "1", "title": "测试资料"}
    assert client.post("/api/resources/upload", headers=student, data=data, files={"file": ("a.md", b"text")}).status_code == 403
    assert client.post("/api/resources/upload", headers=teacher, data=data, files={"file": ("a.exe", b"invalid")}).status_code == 422
    assert client.post("/api/resources/upload", headers=teacher, data=data, files={"file": ("a.txt", b"\xff\xfe\xff")}).status_code == 422
    assert client.post("/api/resources/upload", headers=teacher, data=data, files={"file": ("a.pdf", b"not a pdf")}).status_code == 422
    assert client.post("/api/resources/upload", headers=teacher, data=data, files={"file": ("a.md", b"x" * (10 * 1024 * 1024 + 1))}).status_code == 413


def test_uploaded_video_is_private_and_does_not_expose_storage_key(client):
    teacher = login(client, "teacher")
    student = login(client)
    video = b"synthetic test fixture, not a playable video"
    response = client.post("/api/resources/upload", headers=teacher, data={"course_id": "1", "title": "私有视频"}, files={"file": ("../private.mp4", video, "video/mp4")})
    assert response.status_code == 201
    resource = response.json()
    assert resource["url"] == f"/api/resources/{resource['id']}/file"
    assert "filename" not in resource or "storage_key" not in resource
    assert client.get(resource["url"]).status_code == 401
    assert client.get(resource["url"], headers=student).content == video
    with get_db() as db:
        filename = db.execute("SELECT filename FROM resource_files WHERE resource_id=?", (resource["id"],)).fetchone()[0]
        db.execute("DELETE FROM class_members WHERE student_id=2 AND class_id=1")
    assert client.get(resource["url"], headers=student).status_code == 403
    assert client.get("/media/" + filename).status_code == 404


def test_resource_edit_cannot_change_owning_course(client):
    headers = login(client, "teacher")
    before = client.get("/api/resources?course_id=1", headers=headers).json()[0]
    response = client.patch(f"/api/resources/{before['id']}", headers=headers, json={"course_id": 2, "knowledge_id": 9, "title": "跨课", "kind": "document"})
    assert response.status_code == 422
    assert next(r for r in client.get("/api/resources?course_id=1", headers=headers).json() if r["id"] == before["id"])["version"] == before["version"]


def test_question_cannot_move_and_leave_old_assignment_references(client):
    headers = login(client, "teacher")
    response = client.patch("/api/questions/1", headers=headers, json={"course_id": 2, "knowledge_id": 9, "type": "fill", "title": "不应跨课迁移", "answer": "x"})
    assert response.status_code == 422
    assignment = client.get("/api/assignments/1", headers=headers)
    assert assignment.status_code == 200 and all(q["course_id"] == 1 for q in assignment.json()["questions"])


def test_cannot_delete_knowledge_used_by_existing_assignment(client):
    headers = login(client, "teacher")
    assert client.delete("/api/knowledge/2", headers=headers).status_code == 409
    assert client.get("/api/assignments/1", headers=headers).status_code == 200


def test_invalid_event_cannot_poison_dashboard(client):
    headers = login(client)
    response = client.post("/api/events", headers=headers, json={"course_id": 1, "kind": "video_progress", "payload": {"current_time": "invalid-time"}})
    assert response.status_code == 422
    assert client.get("/api/dashboard", headers=headers).status_code == 200


def test_ai_stream_interruption_has_no_done_and_history_is_explicit(client, monkeypatch):
    async def interrupted(self, messages, **kwargs):
        yield "尚未完成的前半句"
        raise AIError("网络连接中断", code="stream_interrupted")
    monkeypatch.setattr(AIService, "stream", interrupted)
    headers = login(client)
    response = client.post("/api/ai/chat", headers=headers, json={"course_id": 1, "message": "解释栈"})
    assert "event: error" in response.text and "event: done" not in response.text
    metadata = json.loads(response.text.split("data: ")[1].split("\n")[0])
    messages = client.get(f"/api/ai/conversations/{metadata['conversation_id']}", headers=headers).json()["messages"]
    assert messages[-1]["status"] == "interrupted" and messages[-1]["content"] == "尚未完成的前半句"


def test_ai_rate_limit_prevents_provider_request(client, monkeypatch):
    calls = []
    monkeypatch.setenv("AI_MODE", "real")
    monkeypatch.setenv("AI_REQUESTS_PER_MINUTE", "1")
    asyncio.run(ai.limiter.acquire("2", 1))
    def forbidden(*args, **kwargs):
        calls.append(1)
        raise AssertionError("超限请求不应创建HTTP客户端")
    monkeypatch.setattr(ai.httpx, "AsyncClient", forbidden)
    response = client.post("/api/ai/chat", headers=login(client), json={"course_id": 1, "message": "解释栈"})
    assert "rate_limit" in response.text and "event: done" not in response.text
    assert calls == []


def test_provider_eof_before_done_rejected_even_after_partial_content():
    service = AIService(AIConfig(mode="real"), httpx.MockTransport(lambda request: httpx.Response(200, text='data: {"choices":[{"delta":{"content":"前半句"}}]}\n\n')))
    async def collect():
        return [part async for part in service.stream([{"role": "user", "content": "测试"}])]
    with pytest.raises(AIError) as error:
        asyncio.run(collect())
    assert error.value.code == "stream_interrupted"


def test_saved_resource_version_and_retrieval_citations_remain_consistent(client):
    headers = login(client, "teacher")
    resource = client.post("/api/resources", headers=headers, json={"course_id": 1, "knowledge_id": 2, "kind": "document", "title": "专门量子栈讲义", "content": "量子栈是本测试的唯一检索词，版本一内容。"}).json()
    student = login(client)
    response = client.post("/api/ai/chat", headers=student, json={"course_id": 1, "message": "量子栈", "knowledge_id": 2})
    first = json.loads(response.text.split("data: ")[1].split("\n")[0])
    citation = next(c for c in first["citations"] if c["resource_id"] == resource["id"])
    assert citation["version"] == 1 and "版本一" in citation["excerpt"]
    client.patch(f"/api/resources/{resource['id']}", headers=headers, json={"course_id": 1, "knowledge_id": 2, "kind": "document", "title": "专门量子栈讲义", "content": "量子栈是本测试的唯一检索词，版本二已更新。"})
    response = client.post("/api/ai/chat", headers=student, json={"course_id": 1, "message": "量子栈", "knowledge_id": 2})
    second = json.loads(response.text.split("data: ")[1].split("\n")[0])
    citation = next(c for c in second["citations"] if c["resource_id"] == resource["id"])
    assert citation["version"] == 2 and "版本二" in citation["excerpt"]
    historic = client.get(f"/api/ai/conversations/{first['conversation_id']}", headers=student).json()["messages"][-1]["citations"]
    assert next(c for c in historic if c["resource_id"] == resource["id"])["version"] == 1


def test_smoke_restart_and_locks_fail_closed_without_reset(monkeypatch, tmp_path):
    from scripts import ai_smoke
    path = tmp_path / "ledger.json"
    monkeypatch.setattr(ai_smoke, "LEDGER", path)
    first = ai_smoke.reserve("connectivity")
    assert first == 1
    with pytest.raises(SystemExit, match="未确认完成"):
        ai_smoke.reserve("stream")
    assert len(json.loads(path.read_text(encoding="utf-8"))["calls"]) == 1
    ai_smoke.finish(first, "ok")
    with pytest.raises(SystemExit, match="禁止改写历史"):
        ai_smoke.finish(first, "failed")
    path.with_suffix(".lock").write_text("occupied", encoding="utf-8")
    with pytest.raises(SystemExit, match="已有联调进程"):
        ai_smoke.reserve("stream")
    path.with_suffix(".lock").unlink()
    path.with_suffix(".running").write_text("occupied", encoding="utf-8")
    with pytest.raises(SystemExit, match="已有进程"):
        asyncio.run(ai_smoke.run("stream"))


def test_smoke_corrupt_budget_never_silently_reinitializes(monkeypatch, tmp_path):
    from scripts import ai_smoke
    path = tmp_path / "ledger.json"
    monkeypatch.setattr(ai_smoke, "LEDGER", path)
    path.write_text("broken", encoding="utf-8")
    with pytest.raises(SystemExit, match="账本损坏"):
        ai_smoke.reserve("structured")
    assert path.read_text(encoding="utf-8") == "broken"
