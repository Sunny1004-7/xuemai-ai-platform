"""显式开发联调预算，按网络请求预留，保持跨进程和重启累计。"""
from contextlib import contextmanager
import json
import os
import sqlite3
from pathlib import Path


@contextmanager
def ledger():
    root=Path(__file__).resolve().parents[2] / 'data'
    root.mkdir(exist_ok=True)
    db=sqlite3.connect(root/'ai-development-budget.sqlite',timeout=15)
    db.execute('CREATE TABLE IF NOT EXISTS calls(id INTEGER PRIMARY KEY,scope TEXT,model TEXT,status TEXT,usage TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
    try:
        yield db
        db.commit()
    finally:
        db.close()


def reserve(model):
    scope=os.getenv('AI_DEV_BUDGET_SCOPE','')
    if not scope:
        return None
    from .ai import AIError
    with ledger() as db:
        db.execute('BEGIN IMMEDIATE')
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
            db.execute('UPDATE calls SET status=?,usage=? WHERE id=?',(status,json.dumps(usage),call_id))
