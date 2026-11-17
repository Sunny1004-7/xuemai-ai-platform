"""显式开发联调预算，按网络请求预留，保持跨进程和重启累计。"""
from contextlib import contextmanager
import json
import os
import sqlite3
import hashlib
from contextvars import ContextVar
from pathlib import Path

task_id = ContextVar('ai_experiment_task', default='interactive')


@contextmanager
def ledger():
    root=Path(__file__).resolve().parents[2] / 'data'
    root.mkdir(exist_ok=True)
    db=sqlite3.connect(os.getenv('AI_BUDGET_DATABASE', str(root/'ai-development-budget.sqlite')),timeout=15)
    db.execute('CREATE TABLE IF NOT EXISTS calls(id INTEGER PRIMARY KEY,scope TEXT,model TEXT,status TEXT,usage TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
    db.execute('''CREATE TABLE IF NOT EXISTS token_calls(id INTEGER PRIMARY KEY, scope TEXT NOT NULL,
        task_id TEXT NOT NULL, model TEXT NOT NULL, request_hash TEXT NOT NULL,
        reserved INTEGER NOT NULL, charged INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL,
        usage TEXT NOT NULL DEFAULT '{}', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        finished_at TEXT)''')
    db.commit()
    try:
        yield db
        db.commit()
    finally:
        db.close()


def reserve(model, messages=None, max_tokens=768):
    scope=os.getenv('AI_DEV_BUDGET_SCOPE','')
    if not scope:
        return None
    from .ai import AIError
    with ledger() as db:
        db.execute('BEGIN IMMEDIATE')
        token_limit = int(os.getenv('AI_DEV_TOKEN_LIMIT', '0'))
        if token_limit:
            # UTF-8 bytes plus message framing upper-bound ordinary text tokenization.
            # Image requests reserve an additional explicit per-image allowance.
            payload = json.dumps(messages or [], ensure_ascii=False, separators=(',', ':'))
            images = payload.count('image_url')
            estimate = len(payload.encode('utf8')) + 128 + images * 8192
            reserved = estimate + max_tokens
            used = db.execute('''SELECT COALESCE(SUM(CASE WHEN status='reserved' THEN reserved
                ELSE charged END),0) FROM token_calls WHERE scope=?''',(scope,)).fetchone()[0]
            if used + reserved > token_limit:
                raise AIError('本轮真实联调Token预算不足，已停止新请求',429,'development_budget')
            blocked=db.execute("SELECT 1 FROM token_calls WHERE scope=? AND status IN ('authentication','quota')",(scope,)).fetchone()
            if blocked:
                raise AIError('本轮额度或认证异常，已停止请求',503,'development_blocked')
            number=db.execute('''INSERT INTO token_calls(scope,task_id,model,request_hash,reserved,status)
                VALUES(?,?,?,?,?,'reserved')''',(scope,task_id.get(),model,hashlib.sha256(payload.encode()).hexdigest(),reserved)).lastrowid
            return ('tokens', number)
        count=db.execute('SELECT COUNT(*) FROM calls WHERE scope=?',(scope,)).fetchone()[0]
        blocked=db.execute("SELECT 1 FROM calls WHERE scope=? AND status IN ('authentication','quota','provider_rate_limit')",(scope,)).fetchone()
        if blocked:
            raise AIError('本轮联调遇到额度、认证或限流异常，已停止继续请求',503,'development_blocked')
        limit=min(20,int(os.getenv('AI_DEV_REQUEST_LIMIT','20')))
        if count>=limit:
            raise AIError('本轮真实联调请求预算已用完',429,'development_budget')
        return db.execute("INSERT INTO calls(scope,model,status,usage) VALUES(?,?,'reserved','{}')",(scope,model)).lastrowid


def finish(call_id,status,usage):
    if call_id:
        with ledger() as db:
            if isinstance(call_id, tuple):
                number=call_id[1]
                row=db.execute('SELECT reserved,status FROM token_calls WHERE id=?',(number,)).fetchone()
                if row and row[1]=='reserved':
                    # Missing official usage is an uncertain charge, retaining the full reservation.
                    charged = (int(usage.get('prompt_tokens',0))+int(usage.get('completion_tokens',0))
                               if usage and not usage.get('estimated',True) else row[0])
                    db.execute('''UPDATE token_calls SET status=?,usage=?,charged=?,finished_at=CURRENT_TIMESTAMP
                        WHERE id=?''',(status,json.dumps(usage),charged,number))
                return
            db.execute('UPDATE calls SET status=?,usage=? WHERE id=?',(status,json.dumps(usage),call_id))
