"""All AI tests are offline. MockTransport rejects any need for real credentials."""
import asyncio
import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import ai
from backend.app.ai import AIConfig, AIError, AIService, RateLimiter, parse_sse
from backend.app.ai_routes import QuestionDraft, RubricDraft, router
from backend.app.auth import current_user
from backend.app.db import get_db, init_db


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_MODE", "mock")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "offline-test-placeholder")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(ai, "limiter", RateLimiter())
    monkeypatch.setattr(ai, "log_usage", lambda *args, **kwargs: None)


@pytest.fixture
def client():
    init_db()
    application = FastAPI()
    application.include_router(router)
    identity = {"id": 2, "name": "陈星河", "role": "student", "username": "student1"}
    application.dependency_overrides[current_user] = lambda: identity
    with TestClient(application) as test_client:
        yield test_client, identity


def run(coroutine):
    return asyncio.run(coroutine)


def test_mock_never_contacts_transport():
    def forbidden(request):
        raise AssertionError("Mock模式不得发起网络请求")
    service = AIService(AIConfig(), httpx.MockTransport(forbidden))
    assert run(service.complete([{"role": "user", "content": "测试"}], mock_content="本地回答")) == "本地回答"
    assert service.last_usage["completion_tokens"] == 0


def test_real_contract_uses_capped_tokens_without_retry():
    calls = []
    def reply(request):
        payload = json.loads(request.content)
        calls.append(payload)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok":true}'}}],
                                        "usage": {"prompt_tokens": 8, "completion_tokens": 4}})
    service = AIService(AIConfig(mode="real", max_tokens=64), httpx.MockTransport(reply))
    assert json.loads(run(service.complete([{"role": "user", "content": "json"}], json_mode=True, max_tokens=999))) == {"ok": True}
    assert len(calls) == 1
    assert calls[0]["max_tokens"] == 64
    assert calls[0]["thinking"] == {"type": "disabled"}
    assert calls[0]["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("status,code", [(401, "authentication"), (402, "quota"), (429, "provider_rate_limit"), (500, "provider_error")])
def test_provider_errors_do_not_retry_or_echo_sensitive_body(status, code):
    calls = []
    def reply(request):
        calls.append(1)
        return httpx.Response(status, text="sensitive-provider-content")
    service = AIService(AIConfig(mode="real"), httpx.MockTransport(reply))
    with pytest.raises(AIError) as error:
        run(service.complete([{"role": "user", "content": "hello"}]))
    assert error.value.code == code
    assert "sensitive" not in str(error.value)
    assert len(calls) == 1


def test_timeout_is_friendly_and_single_attempt():
    calls = []
    def reply(request):
        calls.append(1)
        raise httpx.ReadTimeout("do not echo private provider detail")
    service = AIService(AIConfig(mode="real"), httpx.MockTransport(reply))
    with pytest.raises(AIError, match="超时") as error:
        run(service.complete([{"role": "user", "content": "hello"}]))
    assert error.value.status_code == 504
    assert len(calls) == 1


@pytest.mark.parametrize("content", ["", "   ", "{bad json", "[]"])
def test_malformed_or_empty_structured_response_rejected(content):
    service = AIService(AIConfig(mode="real"), httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": [{"message": {"content": content}}]})))
    with pytest.raises(AIError):
        run(service.complete([{"role": "user", "content": "json"}], json_mode=True))


class FragmentedStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        content = 'data: {"choices":[{"delta":{"content":"你好"}}]}\n\ndata: {"choices":[{"delta":{"content":"，同学"}}]}\n\ndata: {"choices":[],"usage":{"prompt_tokens":9,"completion_tokens":3}}\n\ndata: [DONE]\n\n'.encode()
        for index in range(0, len(content), 3):
            yield content[index:index + 3]


def test_sse_handles_utf8_fragmentation_and_usage():
    service = AIService(AIConfig(mode="real"), httpx.MockTransport(lambda request: httpx.Response(200, stream=FragmentedStream())))
    async def collect():
        return [part async for part in service.stream([{"role": "user", "content": "测试"}])]
    assert run(collect()) == ["你好", "，同学"]
    assert service.last_usage["completion_tokens"] == 3
    assert service.last_usage["estimated"] is False


def test_malformed_sse_is_not_silently_ignored():
    async def lines():
        yield "data: {broken}"
    async def collect():
        return [item async for item in parse_sse(lines())]
    with pytest.raises(AIError, match="格式异常"):
        run(collect())


def test_rate_limiter_blocks_excess_calls():
    local = RateLimiter()
    async def request():
        await local.acquire("student", 1)
        await local.acquire("student", 1)
    with pytest.raises(AIError) as error:
        run(request())
    assert error.value.status_code == 429


def test_tutor_persists_scoped_context_and_history(client):
    browser, identity = client
    response = browser.post("/api/ai/chat", json={"course_id": 1, "message": "栈和队列的区别", "knowledge_id": 2, "question_id": 1})
    assert response.status_code == 200
    assert "event: delta" in response.text and "event: done" in response.text
    metadata = json.loads(response.text.split("data: ")[1].split("\n")[0])
    assert metadata["mode"] == "mock"
    assert metadata["citations"] and all("栈" in c["excerpt"] or "队列" in c["excerpt"] for c in metadata["citations"])
    conversation = browser.get(f"/api/ai/conversations/{metadata['conversation_id']}").json()
    assert [message["role"] for message in conversation["messages"]] == ["user", "assistant"]
    assert browser.post("/api/ai/chat", json={"course_id": 1, "conversation_id": metadata["conversation_id"], "message": "继续"}).status_code == 200
    identity.update(id=3, username="student2")
    assert browser.get(f"/api/ai/conversations/{metadata['conversation_id']}").status_code == 404


def test_ai_cannot_cross_course_or_question_context(client):
    browser, identity = client
    assert browser.post("/api/ai/chat", json={"course_id": 1, "question_id": 9, "message": "解释"}).status_code == 404
    assert browser.post("/api/ai/chat", json={"course_id": 1, "knowledge_id": 9, "message": "解释"}).status_code == 404
    with get_db() as db:
        db.execute("DELETE FROM class_members WHERE student_id=2 AND class_id=2")
    assert browser.post("/api/ai/chat", json={"course_id": 2, "message": "解释"}).status_code == 403


def test_teacher_drafts_require_review_and_student_cannot_generate(client):
    browser, identity = client
    payload = {"course_id": 1, "kind": "question", "knowledge_id": 2}
    assert browser.post("/api/ai/generate", json=payload).status_code == 403
    identity.update(id=1, role="teacher", username="teacher")
    for kind in ("question", "lesson", "rubric"):
        response = browser.post("/api/ai/generate", json={**payload, "kind": kind, "answer": "示例"})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["draft"] is True and result["review_status"] == "pending_teacher_review"
        assert result["mode"] == "mock" and result["result"]


def test_generated_answer_and_rubric_schema_is_consistent():
    with pytest.raises(ValueError):
        QuestionDraft(type="single", title="足够长的题干", options=["a", "b"], answer="c", explanation="足够长的解析", difficulty=1, hints=["提示"])
    with pytest.raises(ValueError):
        RubricDraft(score=90, criteria=[{"name": "概念", "score": 20, "max_score": 100}], feedback="足够长的反馈")


def test_smoke_reservation_enforces_hard_limit_and_stops_on_failure(monkeypatch, tmp_path):
    from scripts import ai_smoke
    monkeypatch.setattr(ai_smoke, "LEDGER", tmp_path / "ledger.json")
    for _ in range(5):
        number = ai_smoke.reserve("connectivity")
        ai_smoke.finish(number, "ok")
    with pytest.raises(SystemExit, match="硬上限"):
        ai_smoke.reserve("stream")
    record = json.loads(ai_smoke.LEDGER.read_text(encoding="utf-8"))
    assert len(record["calls"]) == 5
    monkeypatch.setattr(ai_smoke, "LEDGER", tmp_path / "failed-ledger.json")
    number = ai_smoke.reserve("connectivity")
    ai_smoke.finish(number, "failed", code="quota")
    with pytest.raises(SystemExit, match="停止真实联调"):
        ai_smoke.reserve("structured")
