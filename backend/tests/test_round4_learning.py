from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_db
from backend.app.evidence import estimate_state
from backend.app.path_planner import order_recommendations
from backend.app.learning_insights import dynamic_groups

NOW = datetime(2026,11,11,tzinfo=timezone.utc)


def test_path_keeps_missing_learning_prerequisite_blocked():
    states = {i:estimate_state(now=NOW) for i in [1,2,3]}
    candidates = [{'knowledge_id':i,'estimated_minutes':8} for i in [2,3]]
    result = order_recommendations(candidates,{1:[],2:[1],3:[]},states)
    assert [r['knowledge_id'] for r in result] == [3]
    states[1] |= {'effective_count':6,'value':.8}
    assert {r['knowledge_id'] for r in order_recommendations(candidates,{1:[],2:[1],3:[]},states)} == {2,3}


def test_classloop_separates_observation_from_diagnosis():
    students = [{'id':i,'features':[.5]*6,'recent_graded_count':0,'feature_confidence':[0]*6} for i in [1,2]]
    questions = [{'id':1,'knowledge_id':1,'skill':'concept','difficulty':1}]
    groups = dynamic_groups(students,questions)
    assert len(groups)==1 and groups[0]['focus']=='补充学习证据'
    assert groups[0]['student_ids']==[1,2]
    assert groups[0]['question_ids']==[1]


def test_classloop_unsupported_dimensions_do_not_form_error_focus():
    students = [{'id':1,'features':[.5,.9,.5,.5,0,0],'recent_graded_count':4,'feature_confidence':[0,1,0,0,1,1]},
                {'id':2,'features':[.5,.8,.5,.5,0,0],'recent_graded_count':4,'feature_confidence':[0,1,0,0,1,1]}]
    groups=dynamic_groups(students,[{'id':2,'knowledge_id':1,'skill':'procedure','difficulty':2}],1)
    assert groups[0]['focus']=='操作步骤'
    assert groups[0]['features']['概念辨析']==0


def test_dashboard_course_switch_and_feedback_match_saved_evidence(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'round4.db'))
    with TestClient(app) as client:
        token=client.post('/api/auth/login',json={'username':'student1','password':'Xuemai123!'}).json()['token']
        headers={'Authorization':'Bearer '+token}
        dashboard=client.get('/api/dashboard?course_id=2',headers=headers).json()
        assert all(r['course_id']==2 for r in dashboard['recommendations'])
        assert all(r['course_id']==2 for r in dashboard['recent_events'])
        assert len(dashboard['courses'])==2
        answer=client.post('/api/attempts',headers=headers,json={'question_id':1,'answer':'3'}).json()
        change=answer['knowledge_change']
        assert change['after']==pytest.approx(answer['evidence']['value']*100,abs=.051)
        with get_db() as db:
            saved=db.execute('SELECT * FROM evidence_updates WHERE attempt_id=?',(answer['id'],)).fetchone()
            assert change['before']==pytest.approx(saved['before_value']*100,abs=.051)
            assert change['weight']==saved['weight']
        again=client.post('/api/attempts',headers=headers,json={'question_id':1,'answer':'3'}).json()
        assert again['knowledge_change']['weight']==0
        assert again['knowledge_change']['after']==again['knowledge_change']['before']
