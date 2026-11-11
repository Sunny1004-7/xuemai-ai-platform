"""Budget-conscious DeepSeek transport. Normal tests never require a network."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import httpx

ROOT = Path(__file__).resolve().parents[2]
MODEL_CAPABILITIES = {
    'deepseek-flash': {'name': 'DeepSeek Flash', 'input_modalities': ['text', 'image']},
    'deepseek-v4-pro': {'name': 'DeepSeek Pro', 'input_modalities': ['text']},
}


def selected_config(model: str | None = None) -> 'AIConfig':
    config = AIConfig.from_env()
    selected = model or 'deepseek-flash'
    if selected not in MODEL_CAPABILITIES:
        raise AIError('请选择 DeepSeek Flash 或 Pro', 422, 'invalid_model')
    return replace(config, model=selected)


class AIError(Exception):
    def __init__(self, message: str, status_code: int = 502, code: str = "provider_error"):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def read_backend_key() -> str:
    """Read local credentials only in the server. Never return them from an API."""
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not key:
        path = ROOT / "deepseek官方api.txt"
        if path.is_file():
            match = re.search(r"sk-[A-Za-z0-9_-]+", path.read_text(encoding="utf-8-sig"))
            if match:
                key = match.group(0)
                os.environ["DEEPSEEK_API_KEY"] = key
    return key


def bounded_env(name: str, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(os.getenv(name, str(default)))))
    except ValueError:
        return default


@dataclass(frozen=True)
class AIConfig:
    mode: str = "mock"
    model: str = "deepseek-flash"
    base_url: str = "https://api.deepseek.com"
    max_tokens: int = 768
    timeout: float = 35
    requests_per_minute: int = 6

    @classmethod
    def from_env(cls) -> "AIConfig":
        mode = os.getenv("AI_MODE", "auto").lower()
        if mode == "auto":
            mode = "real" if read_backend_key() else "mock"
        if mode not in {"mock", "real"}:
            raise AIError("AI_MODE 只能为 auto、mock 或 real", 503, "configuration")
        base = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        if base != "https://api.deepseek.com":
            raise AIError("真实 AI 服务只允许 DeepSeek 官方 HTTPS 地址", 503, "configuration")
        return cls(
            mode=mode,
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-flash"),
            base_url=base,
            max_tokens=bounded_env("AI_MAX_TOKENS", 768, 32, 4096),
            timeout=bounded_env("AI_TIMEOUT_SECONDS", 35, 3, 120),
            requests_per_minute=bounded_env("AI_REQUESTS_PER_MINUTE", 6, 1, 30),
        )


class RateLimiter:
    def __init__(self):
        self.requests: dict[str, deque[float]] = defaultdict(deque)
        self.lock = asyncio.Lock()

    async def acquire(self, key: str, limit: int) -> None:
        async with self.lock:
            now = time.monotonic()
            items = self.requests[key]
            while items and now - items[0] >= 60:
                items.popleft()
            if len(items) >= limit:
                raise AIError("请求较频繁，请一分钟后再试", 429, "rate_limit")
            items.append(now)


limiter = RateLimiter()


def safe_usage(usage: dict | None, messages: list[dict], content: str) -> dict:
    usage = usage or {}
    return {
        "prompt_tokens": int(usage.get("prompt_tokens", sum(len(str(m["content"])) for m in messages) // 2)),
        "completion_tokens": int(usage.get("completion_tokens", len(content) // 2)),
        "estimated": not bool(usage),
    }


def log_usage(config: AIConfig, kind: str, usage: dict, status: str, elapsed: float) -> None:
    path = ROOT / "data" / "ai-usage.jsonl"
    path.parent.mkdir(exist_ok=True)
    record = {"at": datetime.now(timezone.utc).isoformat(), "mode": config.mode, "model": config.model,
              "kind": kind, "scope": os.getenv("AI_USAGE_SCOPE", "product"), "status": status, "duration_ms": round(elapsed * 1000), **usage}
    # No credentials, prompts, personal data or raw provider errors enter the log.
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def provider_error(status: int) -> AIError:
    if status in {402, 403}:
        return AIError("AI 服务额度或权限不足，已停止请求，请联系教师；可继续本地学习", 503, "quota")
    if status == 401:
        return AIError("AI 服务凭据未通过验证，请由管理员检查后端配置", 503, "authentication")
    if status == 429:
        return AIError("AI 服务暂时限流，请稍后重试；本次不会自动重发", 429, "provider_rate_limit")
    return AIError("AI 服务暂不可用，请稍后重试；本次不会自动重发", 502)


async def parse_sse(lines: AsyncIterator[str]) -> AsyncIterator[dict]:
    """httpx aiter_lines handles arbitrary UTF-8/network chunk boundaries."""
    async for line in lines:
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            return
        if not payload:
            continue
        try:
            item = json.loads(payload)
        except json.JSONDecodeError as error:
            raise AIError("AI 流式响应格式异常，请重新提问", 502, "invalid_response") from error
        if not isinstance(item, dict):
            raise AIError("AI 流式响应格式异常", 502, "invalid_response")
        if item.get("error"):
            raise AIError("AI 流式响应中断，请稍后重试", 502, "stream_error")
        yield item
    raise AIError("AI 流式连接提前关闭，回答尚未完成，请重新提问", 502, "stream_interrupted")


class AIService:
    def __init__(self, config: AIConfig | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.config = config or AIConfig.from_env()
        self.transport = transport
        self.last_usage: dict = {}

    def payload(self, messages: list[dict], *, stream: bool = False, json_mode: bool = False,
                max_tokens: int | None = None) -> dict:
        value = {"model": self.config.model, "messages": messages, "stream": stream,
                 "thinking": {"type": "disabled"}, "temperature": 0.3,
                 "max_tokens": min(max_tokens or self.config.max_tokens, self.config.max_tokens)}
        if json_mode:
            value["response_format"] = {"type": "json_object"}
        if stream:
            value["stream_options"] = {"include_usage": True}
        return value

    def headers(self) -> dict:
        key = read_backend_key()
        if not key:
            raise AIError("AI 服务尚未配置密钥，请由管理员配置后端环境变量", 503, "not_configured")
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    async def complete(self, messages: list[dict], *, user_key: str = "system", json_mode: bool = False,
                       mock_content: str = "", max_tokens: int | None = None) -> str:
        started = time.monotonic()
        self.last_usage = {}
        await limiter.acquire(user_key, self.config.requests_per_minute)
        content = ""
        status = "error"
        from .ai_budget import reserve, finish
        reservation = reserve(self.config.model) if self.config.mode == 'real' else None
        try:
            if self.config.mode == "mock":
                content = mock_content or "这是本地演示回答。先确定输入和边界条件，再逐步验证你的思路。"
                self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0, "estimated": False}
            else:
                async with httpx.AsyncClient(timeout=self.config.timeout, transport=self.transport) as client:
                    response = await client.post(f"{self.config.base_url}/chat/completions", headers=self.headers(),
                                                 json=self.payload(messages, json_mode=json_mode, max_tokens=max_tokens))
                if response.status_code != 200:
                    raise provider_error(response.status_code)
                try:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    if not isinstance(content, str) or not content.strip():
                        raise ValueError("empty")
                    self.last_usage = safe_usage(data.get("usage"), messages, content)
                except (ValueError, KeyError, IndexError, TypeError) as error:
                    raise AIError("AI 返回内容为空或格式异常，请缩小问题范围后再试", 502, "invalid_response") from error
            if json_mode:
                try:
                    if not isinstance(json.loads(content), dict):
                        raise ValueError("not object")
                except ValueError as error:
                    raise AIError("AI 结构化结果未通过 JSON 校验，草稿未保存", 502, "invalid_json") from error
            status = "ok"
            return content
        except AIError as error:
            status=error.code
            raise
        except httpx.TimeoutException as error:
            raise AIError("AI 响应超时，可稍后重新提问；本次不会自动重发", 504, "timeout") from error
        except httpx.HTTPError as error:
            raise AIError("无法连接 AI 服务，请检查网络后重试", 502, "network") from error
        finally:
            if not self.last_usage:
                self.last_usage = safe_usage(None, messages, content)
            log_usage(self.config, "json" if json_mode else "chat", self.last_usage,
                      status, time.monotonic() - started)
            finish(reservation,status,self.last_usage)

    async def stream(self, messages: list[dict], *, user_key: str = "system", mock_content: str = "",
                     max_tokens: int | None = None) -> AsyncIterator[str]:
        started = time.monotonic()
        self.last_usage = {}
        await limiter.acquire(user_key, self.config.requests_per_minute)
        content = ""
        usage = None
        status = "error"
        finish_reason = None
        from .ai_budget import reserve, finish
        reservation = reserve(self.config.model) if self.config.mode == 'real' else None
        try:
            if self.config.mode == "mock":
                answer = mock_content or "先确定问题的输入，再用一个小例子逐步验证。你认为第一步应该做什么？"
                for offset in range(0, len(answer), 8):
                    fragment = answer[offset:offset + 8]
                    content += fragment
                    await asyncio.sleep(0.012)
                    yield fragment
                self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0, "estimated": False}
            else:
                async with httpx.AsyncClient(timeout=self.config.timeout, transport=self.transport) as client:
                    async with client.stream("POST", f"{self.config.base_url}/chat/completions", headers=self.headers(),
                                             json=self.payload(messages, stream=True, max_tokens=max_tokens)) as response:
                        if response.status_code != 200:
                            raise provider_error(response.status_code)
                        async for item in parse_sse(response.aiter_lines()):
                            if item.get("usage"):
                                usage = item["usage"]
                            choices = item.get("choices") or []
                            if not isinstance(choices, list):
                                raise AIError("AI 流式响应格式异常", 502, "invalid_response")
                            if choices:
                                if not isinstance(choices[0], dict) or not isinstance(choices[0].get("delta", {}), dict):
                                    raise AIError("AI 流式响应格式异常", 502, "invalid_response")
                                finish_reason = choices[0].get("finish_reason") or finish_reason
                                fragment = choices[0].get("delta", {}).get("content") or ""
                                if not isinstance(fragment, str):
                                    raise AIError("AI 流式文本格式异常", 502, "invalid_response")
                                content += fragment
                                if fragment:
                                    yield fragment
                if not content.strip():
                    raise AIError("AI 未返回有效回答，请缩小问题范围后再试", 502, "empty_response")
                self.last_usage = safe_usage(usage, messages, content)
                if finish_reason == "length":
                    raise AIError("回答达到输出长度上限，尚未完整结束；请缩小问题范围后继续", 502, "truncated")
            status = "ok"
        except AIError as error:
            status=error.code
            raise
        except httpx.TimeoutException as error:
            raise AIError("AI 响应超时，已保留提问，可稍后重试", 504, "timeout") from error
        except httpx.HTTPError as error:
            raise AIError("AI 网络连接中断，可稍后重新提问", 502, "network") from error
        finally:
            if not self.last_usage:
                self.last_usage = safe_usage(usage, messages, content)
            log_usage(self.config, "stream", self.last_usage,
                      status, time.monotonic() - started)
            finish(reservation,status,self.last_usage)
