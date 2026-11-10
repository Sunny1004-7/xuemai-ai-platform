"""隔离合成场景验证模型性质，不估计真实教学效果。"""
from datetime import datetime, timedelta, timezone
import json
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_db
from backend.app.evidence import estimate_state, update_state, schedule_review
from backend.app.retrieval import retrieve, sync_index
from backend.app.teaching_actions import validate_selection, MARKER

@pytest.fixture()
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'evidence.db'))
    monkeypatch.setenv('AI_MODE','mock')
    with TestClient(app) as c:yield c


def login(client,username='student1'):
    return {'Authorization':'Bearer '+client.post('/api/auth/login',json={'username':username,'password':'Xuemai123!'}).json()['token']}


def test_prerequisite_path_and_error_diagnosis(client):
    h=login(client)
    plans=client.get('/api/recommendations',headers=h).json()
    quick=next(r for r in plans if r['knowledge_id']==7)
    assert quick['prerequisite_ids'] and quick['steps'][0]['kind']=='prerequisite'
    assert [s['kind'] for s in quick['steps']][-3:]==['practice','check','review']
    wrong=client.post('/api/attempts',headers=h,json={'question_id':1,'answer':'1'}).json()
    assert wrong['error_type']=='入栈与出栈顺序混淆'


def test_repeated_success_preserves_evidence_clock(client):
    h=login(client)
    client.post('/api/attempts',headers=h,json={'question_id':3,'answer':'最大元素'})
    with get_db() as db:
        before=dict(db.execute('SELECT * FROM mastery WHERE student_id=2 AND knowledge_id=6').fetchone())
    client.post('/api/attempts',headers=h,json={'question_id':3,'answer':'最大元素'})
    with get_db() as db:
        after=dict(db.execute('SELECT * FROM mastery WHERE student_id=2 AND knowledge_id=6').fetchone())
        assert after==before
        assert db.execute('SELECT weight FROM evidence_updates ORDER BY id DESC LIMIT 1').fetchone()[0]==0


def test_incremental_index_versions_and_no_rebuild(client):
    teacher=login(client,'teacher')
    with get_db() as db:
        assert sync_index(db)==0
        before=db.total_changes
        hits=retrieve(db,1,'循环队列',12)
        assert any('循环队列' in c['title'] for c in hits)
        assert db.total_changes==before
    created=client.post('/api/resources',headers=teacher,json={'course_id':1,'title':'队列边界验证','kind':'document','content':'环形队列使用取模操作。'}).json()
    rid=created['id']
    client.patch(f'/api/resources/{rid}',headers=teacher,json={'content':'环形队列空满判定采用保留空位策略。'})
    with get_db() as db:
        hits=retrieve(db,1,'空满判定保留空位')
        match=next(c for c in hits if c['resource_id']==rid)
        assert match['version']==2 and '保留空位' in match['excerpt']
        assert sync_index(db)==0


def test_understanding_check_scores_and_changes_next_action(client):
    h=login(client)
    text=client.post('/api/ai/chat',headers=h,json={'course_id':1,'knowledge_id':2,'question_id':1,'message':'我还分不清栈与队列，请对照讲解。'}).text
    done=json.loads(text.split('event: done\ndata: ')[1].split('\n')[0])
    plan=done['teaching']
    assert plan['actions'] and plan['check']
    assert MARKER not in text
    check_id=plan['check']['id']
    result=client.post(f'/api/ai/checks/{check_id}/answer',headers=h,json={'answer':'不确定'}).json()
    assert result['correct'] is False and '/graph?' in result['next_action']['href']
    assert result['review_schedule']['last_quality']==1
    saved=client.get(f'/api/ai/checks/{check_id}',headers=h).json()
    assert saved['result']['correct']==0
    with get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM learning_events WHERE kind='understanding_check'").fetchone()[0]==1


def test_assignment_captures_baseline_and_returns_actual_evidence(client):
    teacher=login(client,'teacher');student=login(client)
    task=client.post('/api/assignments',headers=teacher,json={'course_id':1,'title':'栈迁移巩固','knowledge_id':2,'question_ids':[2],'student_ids':[2]}).json()
    client.post('/api/attempts',headers=student,json={'question_id':2,'answer':['函数调用','括号匹配','撤销操作'],'assignment_id':task['id']})
    results=client.get(f"/api/assignments/{task['id']}/results",headers=teacher).json()[0]
    assert results['completed'] and results['comparison'][0]['delta']>0
    assert results['comparison'][0]['new_evidence']>0


@pytest.mark.parametrize('selection',[{'strategy':'contrast','kinds':['contrast']},{'kinds':['unknown']},{}])
def test_model_selection_maps_only_supported_actions(selection):
    plan={'strategy':'hint','actions':[{'kind':'contrast','href':'/graph?knowledge=2'},{'kind':'check','check_id':1}]}
    content,result=validate_selection('先看状态变化。'+MARKER+json.dumps(selection)+'-->',plan)
    assert content=='先看状态变化。'
    assert all(a['kind'] in ('contrast','check') for a in result['actions'])
    assert any(a['kind']=='check' for a in result['actions'])
