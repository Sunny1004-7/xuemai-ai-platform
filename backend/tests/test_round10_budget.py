"""Token预留、故障保守结算与跨连接累计回归，全部离线。"""
import pytest
from backend.app.ai import AIError
from backend.app.ai_budget import reserve, finish, ledger


@pytest.fixture(autouse=True)
def budget(monkeypatch, tmp_path):
    monkeypatch.setenv('AI_BUDGET_DATABASE', str(tmp_path/'ledger.db'))
    monkeypatch.setenv('AI_DEV_BUDGET_SCOPE','round10-test')
    monkeypatch.setenv('AI_DEV_TOKEN_LIMIT','1000')


def test_reservation_includes_other_inflight_requests():
    first=reserve('deepseek-flash', [], 400)
    with pytest.raises(AIError,match='预算'):
        reserve('deepseek-flash', [], 400)
    finish(first,'ok',{'prompt_tokens':20,'completion_tokens':30,'estimated':False})
    assert reserve('deepseek-flash', [], 400)


def test_unknown_failure_retains_worst_case_and_finish_is_idempotent():
    first=reserve('deepseek-flash', [], 400)
    finish(first,'network',{'estimated':True,'prompt_tokens':1})
    finish(first,'ok',{'estimated':False,'prompt_tokens':1})
    with ledger() as db:
        row=db.execute('SELECT reserved,charged,status FROM token_calls').fetchone()
    assert row==(530,530,'network')


def test_official_usage_counts_reasoning_once_and_cache_input():
    first=reserve('deepseek-v4-pro', [], 200)
    finish(first,'ok',{'prompt_tokens':50,'completion_tokens':100,'reasoning_tokens':60,
                       'prompt_cache_hit_tokens':20,'estimated':False})
    with ledger() as db:
        assert db.execute('SELECT charged FROM token_calls').fetchone()[0]==150


def test_failed_large_input_rejected_without_insert():
    with pytest.raises(AIError):
        reserve('deepseek-flash',[{'role':'user','content':'汉'*500}],100)
    with ledger() as db:
        assert db.execute('SELECT COUNT(*) FROM token_calls').fetchone()[0]==0


def test_concurrent_reservations_share_one_ceiling():
    from concurrent.futures import ThreadPoolExecutor
    def attempt(_):
        try:
            return reserve('deepseek-flash',[],200)
        except AIError:
            return None
    with ThreadPoolExecutor(max_workers=8) as executor:
        accepted=[value for value in executor.map(attempt,range(16)) if value]
    assert len(accepted)==3
    with ledger() as db:
        assert db.execute('SELECT SUM(reserved) FROM token_calls').fetchone()[0]==990
