from datetime import datetime, timezone
import json
import pytest
from fastapi.testclient import TestClient
from backend.app.db import get_db, init_db
from backend.app.main import app
from backend.app.evidence import estimate_state, update_state
from backend.app.path_planner import plan_path
from backend.app.learning_insights import dynamic_groups

NOW=datetime(2026,11,10,tzinfo=timezone.utc)


def test_ktrace_correlated_variants_and_partial_teacher_score():
    state=estimate_state(now=NOW)
    independent=update_state(state,True,2,0,now=NOW)
    correlated=update_state(state,True,2,0,now=NOW,peer_count=8)
    partial=update_state(state,True,2,0,now=NOW,score=65)
    hinted=update_state(state,True,2,2,now=NOW)
    assert independent['weight'] > correlated['weight']
    assert independent['value'] > partial['value'] > hinted['value']
    assert not state['observed']
    assert partial['quality']==.65


def test_pathg_prerequisite_budget_and_goal_replanning():
    states={i:estimate_state(now=NOW) for i in range(1,5)}
    parents={1:[],2:[1],3:[],4:[3]}
    items=[{'knowledge_id':i,'estimated_minutes':8,'goal':i==2} for i in range(1,5)]
    plan=plan_path(items,parents,states,budget=16)
    assert plan['knowledge_ids']==[1,2]
    assert plan['minutes']<=16
    other=plan_path([c|{'goal':c['knowledge_id']==4} for c in items],parents,states,budget=16)
    assert other['knowledge_ids']==[3,4]
    # 静态目标优先排序把后续知识置于其先修之前。
    baseline=sorted(items,key=lambda c:not c['goal'])
    assert baseline[0]['knowledge_id']==2
    assert plan['knowledge_ids'].index(1)<plan['knowledge_ids'].index(2)


def test_classloop_equal_scores_different_errors_and_dynamic_membership():
    students=[{'id':i+1,'features':v} for i,v in enumerate([[.9,.1,.1,.1,0,0],[.8,.1,.1,.1,0,0],[.1,.9,.1,.1,0,0],[.1,.8,.1,.1,0,0]])]
    questions=[{'id':1,'knowledge_id':1,'skill':'concept','difficulty':2},{'id':2,'knowledge_id':2,'skill':'procedure','difficulty':2}]
    groups=dynamic_groups(students,questions,2)
    assert {frozenset(g['student_ids']) for g in groups}=={frozenset([1,2]),frozenset([3,4])}
    changed=[s|{'features':[.1,.9,.1,.1,0,0]} if s['id']==2 else s for s in students]
    after=dynamic_groups(changed,questions,2)
    assert any(set(g['student_ids'])=={2,3,4} for g in after)
    assert {g['focus'] for g in groups}=={'概念辨析','操作步骤'}


def login(client,name='student1'):
    return {'Authorization':'Bearer '+client.post('/api/auth/login',json={'username':name,'password':'Xuemai123!'}).json()['token']}


def test_cohort_idempotence_chronology_and_teacher_student_views(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'cohort.db'))
    monkeypatch.setenv('XUEMAI_DEMO_COHORT','1')
    with TestClient(app) as client:
        teacher=login(client,'teacher')
        data=client.get('/api/analytics?course_id=1',headers=teacher).json()
        assert data['summary']['student_count']==28
        assert len(data['heatmap'])==28 and len(data['heatmap'][0]['cells'])==31
        assert len({s['accuracy'] for s in data['students']})>10
        assert sum(len(g['student_ids']) for g in data['groups'])==28
        with get_db() as db:
            before=db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]
            assert before>1500
            assert db.execute('SELECT COUNT(*) FROM attempts a JOIN assignments t ON t.id=a.assignment_id WHERE julianday(a.created_at)<julianday(t.created_at)').fetchone()[0]==0
            assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
        init_db()
        with get_db() as db:
            assert db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]==before
        student=login(client)
        insights=client.get('/api/learning/insights?course_id=1',headers=student).json()
        row=next(r for r in data['students'] if r['id']==2)
        assert insights['students'][0]['mastery']==row['mastery']
        assert client.get('/api/analytics',headers=student).status_code==403


def test_diaguide_persists_three_roles_and_adapts_after_failed_check(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'agents.db'))
    with TestClient(app) as client:
        headers=login(client)
        def ask(conversation=None):
            text=client.post('/api/ai/chat',headers=headers,json={'course_id':1,'knowledge_id':2,'message':'我分不清出栈顺序，请引导我。','conversation_id':conversation}).text
            return json.loads(text.split('event: done\ndata: ')[1].split('\n')[0])
        first=ask()
        shared=first['teaching']['collaboration']
        assert [s['role'] for s in shared['trace']]==['学习诊断代理','教学策略代理','教学校验代理']
        assert shared['verification']['passed']
        check=first['teaching']['check']['id']
        result=client.post(f'/api/ai/checks/{check}/answer',headers=headers,json={'answer':'不确定'}).json()
        assert result['collaboration']['feedback']['correct'] is False
        second=ask(first['conversation_id'])
        assert second['teaching']['strategy']=='experiment'
        assert second['teaching']['collaboration']['diagnosis']['previous_feedback']['attempt_id']==result['id']
        with get_db() as db:
            assert db.execute("SELECT COUNT(*) FROM teaching_runs WHERE status='feedback'").fetchone()[0]==1
