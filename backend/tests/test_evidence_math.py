"""证据估计与间隔调度的确定性数学性质。"""
from datetime import datetime,timedelta,timezone
import pytest
from backend.app.evidence import estimate_state,update_state,schedule_review

NOW = datetime(2026,11,10,tzinfo=timezone.utc)


@pytest.mark.parametrize('difficulty',[1,2,3])
def test_hint_quality_is_lower_than_independent(difficulty):
    state=estimate_state(now=NOW)
    independent=update_state(state,True,difficulty,0,now=NOW)
    hinted=update_state(state,True,difficulty,2,now=NOW)
    assert independent['value']>hinted['value']
    assert hinted['quality']==pytest.approx(1/3)


def test_same_item_success_adds_no_weight_but_error_is_recorded():
    state=estimate_state(now=NOW)
    previous={'correct':1,'created_at':(NOW-timedelta(hours=1)).isoformat()}
    assert update_state(state,True,3,0,previous,NOW)['weight']==0
    assert update_state(state,False,3,0,previous,NOW)['weight']>0


def test_long_gap_restores_item_weight():
    state=estimate_state(now=NOW)
    previous={'correct':1,'created_at':(NOW-timedelta(days=2)).isoformat()}
    assert update_state(state,True,3,0,previous,NOW)['weight']==1.8


def test_decay_returns_towards_prior_and_widens_uncertainty():
    row={'alpha':12,'beta':4,'effective_count':12,'updated_at':NOW.isoformat()}
    recent=estimate_state(row,NOW)
    later=estimate_state(row,NOW+timedelta(days=90))
    assert .25<later['value']<recent['value']
    assert later['effective_count']==pytest.approx(1.5)
    assert later['upper']-later['lower']>recent['upper']-recent['lower']


def test_review_intervals_follow_quality_and_repetition():
    first=schedule_review(None,True,0,False,NOW)
    second=schedule_review(first,True,0,False,NOW+timedelta(days=1))
    third=schedule_review(second,True,0,False,NOW+timedelta(days=7))
    assert (first['interval_days'],second['interval_days'])==(1,6)
    assert third['interval_days']>6
    failed=schedule_review(third,False,0,False,NOW+timedelta(days=20))
    assisted=schedule_review(third,True,1,False,NOW+timedelta(days=20))
    assert failed['interval_days']==1 and failed['repetitions']==0
    assert assisted['interval_days']<=2
    assert schedule_review(third,True,0,True,NOW)==third


