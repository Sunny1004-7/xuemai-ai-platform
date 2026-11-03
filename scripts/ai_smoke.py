"""Explicit, serialized, reserve-before-send real API sampling (never part of CI)."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.ai import AIConfig, AIError, AIService, read_backend_key

LEDGER = ROOT / "data" / "ai-smoke-ledger.json"


def read_ledger() -> dict:
    if not LEDGER.exists():
        return {"limit": 5, "calls": [], "halted": False}
    try:
        record = json.loads(LEDGER.read_text(encoding="utf-8"))
        calls = record["calls"]
        if not isinstance(calls, list) or not isinstance(record.get("halted"), bool):
            raise ValueError("invalid ledger")
        for index, call in enumerate(calls, 1):
            if call["number"] != index or call["kind"] not in {"connectivity", "stream", "structured"} or call["status"] not in {"reserved", "ok", "failed"}:
                raise ValueError("invalid call")
        return record
    except (ValueError, KeyError, TypeError):
        raise SystemExit("真实联调账本损坏或格式异常，已阻止发送；请核实既有计数，不能直接重置账本")


def write_ledger(record: dict):
    # Atomic replacement prevents a crash from silently truncating the budget.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=LEDGER.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(record, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, LEDGER)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def reserve(kind: str) -> int:
    LEDGER.parent.mkdir(exist_ok=True)
    lock = LEDGER.with_suffix(".lock")
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError:
        raise SystemExit("已有联调进程运行；为避免并发消耗，本次未发送请求")
    try:
        with handle:
            record = read_ledger()
            if record.get("halted"):
                raise SystemExit("先前出现额度、凭据或服务异常，已停止真实联调；本次未发送请求")
            if any(call["status"] == "reserved" for call in record["calls"]):
                raise SystemExit("上次真实联调未确认完成，已保留计数并停止后续调用；请先核实外部状态")
            hard_limit = min(5, max(0, int(os.getenv("AI_SMOKE_CALL_LIMIT", "5"))))
            if len(record["calls"]) >= hard_limit:
                raise SystemExit("真实联调额度已达硬上限；本次未发送请求")
            record["limit"] = hard_limit
            record["calls"].append({"number": len(record["calls"]) + 1, "kind": kind,
                                    "reserved_at": datetime.now(timezone.utc).isoformat(), "status": "reserved", "max_output_tokens": 256})
            write_ledger(record)
            return len(record["calls"])
    finally:
        lock.unlink(missing_ok=True)


def finish(number: int, status: str, usage: dict | None = None, code: str = ""):
    record = read_ledger()
    if not 1 <= number <= len(record["calls"]) or record["calls"][number - 1]["status"] != "reserved":
        raise SystemExit("联调结果与已预留调用不一致，禁止改写历史")
    record["calls"][number - 1].update(status=status, usage=usage or {}, error_code=code,
                                       finished_at=datetime.now(timezone.utc).isoformat())
    # No automatic retry after any failure; ordinary regression can still run locally.
    if status != "ok":
        record["halted"] = True
    write_ledger(record)


async def run_once(kind: str):
    if not read_backend_key():
        raise SystemExit("未配置后端密钥；未占用联调次数，未发送请求")
    config = AIConfig(mode="real", model=os.getenv("DEEPSEEK_MODEL", "deepseek-flash"), max_tokens=256, timeout=35)
    service = AIService(config)
    number = reserve(kind)
    try:
        if kind == "connectivity":
            content = await service.complete([{"role": "user", "content": "请用一句中文说明栈的后进先出，不超过30字。"}], max_tokens=64)
            if not content.strip():
                raise AIError("空响应", code="invalid_response")
        elif kind == "stream":
            fragments = []
            async for part in service.stream([{"role": "system", "content": "你是课程辅导老师，用渐进提示，不超过80字。"},
                                              {"role": "user", "content": "队列和栈有什么区别？请给一个理解检查问题。"}], max_tokens=180):
                fragments.append(part)
            if not fragments:
                raise AIError("无流式片段", code="invalid_response")
        else:
            content = await service.complete([{"role": "system", "content": '只输出 json 对象，样例 {"question":"判断题题干","answer":true,"explanation":"一句解释"}。'},
                                              {"role": "user", "content": "生成一道关于栈后进先出的判断题。"}], json_mode=True, max_tokens=180)
            result = json.loads(content)
            if not isinstance(result.get("question"), str) or not isinstance(result.get("answer"), bool) or not isinstance(result.get("explanation"), str):
                raise AIError("结构化样例校验失败", code="schema")
        finish(number, "ok", service.last_usage)
        print(json.dumps({"call": number, "kind": kind, "status": "ok", "model": config.model, "usage": service.last_usage}, ensure_ascii=False))
    except AIError as error:
        finish(number, "failed", service.last_usage, error.code)
        print(json.dumps({"call": number, "kind": kind, "status": "failed", "error_code": error.code,
                          "message": str(error), "further_calls_halted": True}, ensure_ascii=False))
        raise SystemExit(1)
    except Exception:
        # Raw transport errors can contain credentials/URLs; never print traceback.
        finish(number, "failed", service.last_usage, "unexpected")
        print("联调异常，后续真实调用已停止；请通过本地 Mock 排查")
        raise SystemExit(1)


async def run(kind: str):
    LEDGER.parent.mkdir(exist_ok=True)
    running = LEDGER.with_suffix(".running")
    try:
        handle = running.open("x", encoding="utf-8")
    except FileExistsError:
        raise SystemExit("真实联调已有进程运行或先前中断；本次未发送请求。核实先前进程结束后才能清理 data/ai-smoke-ledger.running")
    try:
        with handle:
            await run_once(kind)
    finally:
        running.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="少量真实 DeepSeek 联调，需显式执行；所有普通测试不运行本脚本")
    parser.add_argument("--kind", choices=["connectivity", "stream", "structured"], required=True)
    parser.add_argument("--run", action="store_true", help="明确发送一次计费请求")
    arguments = parser.parse_args()
    if not arguments.run:
        parser.error("未指定 --run；未发送任何请求")
    asyncio.run(run(arguments.kind))
