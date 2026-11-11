"""第五轮的内容升级、规划预算与事件完成业务验证；全部在隔离数据库执行。"""
import json
import pytest
from backend.app.db import get_db,init_db
from backend.app.learning import recommendations,record_attempt
from backend.app.routes_plans import PlanBody,create_plan,plans
from backend.app.learning_insights import dynamic_groups
from backend.app.evidence import estimate_state
from backend.app.path_planner import plan_path


@pytest.fixture()
def full(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'full.db'))
    monkeypatch.setenv('XUEMAI_DEMO_COHORT','1')
    init_db()
    return tmp_path


def counts(db):
    return {t:db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ['users','questions','attempts','evidence_updates','learning_events','study_plans','ai_messages','sample_entities']}


def test_fresh_content_and_repeated_upgrade_preserve_edit(full):
    from scripts.check_content_coverage import inspect
    with get_db() as db:
        report=inspect(db)
        assert report['passed'],report
        before=counts(db)
        rid=db.execute("SELECT id FROM resources WHERE course_id=2 AND kind='document' LIMIT 1").fetchone()[0]
        db.execute('UPDATE resources SET content=? WHERE id=?',('教师人工保留的讲义修订',rid))
    init_db();init_db()
    with get_db() as db:
        assert counts(db)==before
        assert db.execute('SELECT content FROM resources WHERE id=?',(rid,)).fetchone()[0]=='教师人工保留的讲义修订'
        # 模拟内容包完成标记丢失，实体稳定键仍阻止重复事件与评分。
        db.execute('DELETE FROM sample_packages')
    init_db()
    with get_db() as db:assert counts(db)==before


def test_round4_database_upgrade(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'upgrade.db'))
    init_db() # 精简第四轮已有课程、题目与作答，尚未导入本轮内容。
    with get_db() as db:
        db.execute("UPDATE resources SET content='升级前人工编辑' WHERE id=1")
        previous=db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]
    monkeypatch.setenv('XUEMAI_DEMO_COHORT','1');init_db()
    from scripts.check_content_coverage import inspect
    with get_db() as db:
        assert inspect(db)['passed']
        assert db.execute('SELECT content FROM resources WHERE id=1').fetchone()[0]=='升级前人工编辑'
        assert db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]>=previous


def test_sample_text_upgrade_preserves_edited_conversation(tmp_path,monkeypatch):
    from backend.app import sample_dialogues
    refine=sample_dialogues.refine_sample_text
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'text-upgrade.db'))
    monkeypatch.setenv('XUEMAI_DEMO_COHORT','1')
    monkeypatch.setattr(sample_dialogues,'refine_sample_text',lambda db:None)
    init_db()
    with get_db() as db:
        conv=db.execute("SELECT entity_id FROM sample_entities WHERE sample_key='v5:CS101:conversation:0'").fetchone()[0]
        messages=db.execute('SELECT id,content FROM ai_messages WHERE conversation_id=? ORDER BY id',(conv,)).fetchall()
        db.execute('UPDATE ai_messages SET content=? WHERE id=?',('学生补充了自己的思考，请保留',messages[0]['id']))
        before=[dict(r) for r in db.execute('SELECT * FROM ai_messages WHERE conversation_id=? ORDER BY id',(conv,))]
    monkeypatch.setattr(sample_dialogues,'refine_sample_text',refine)
    init_db();init_db()
    with get_db() as db:
        assert [dict(r) for r in db.execute('SELECT * FROM ai_messages WHERE conversation_id=? ORDER BY id',(conv,))]==before
        untouched=db.execute("SELECT c.title FROM ai_conversations c JOIN sample_entities e ON e.entity_id=c.id WHERE e.sample_key='v5:CS101:conversation:1'").fetchone()[0]
        assert untouched=='修改副本为何影响原列表'
        assert db.execute('SELECT COUNT(*) FROM sample_packages WHERE version=5002').fetchone()[0]==1


@pytest.mark.parametrize('minutes',[10,30,60])
def test_goal_budget_reaches_pathg(full,monkeypatch,minutes):
    with get_db() as db:
        db.execute('UPDATE learning_goals SET daily_minutes=? WHERE student_id=2 AND course_id=2 AND status=?',(minutes,'active'))
        user=dict(db.execute('SELECT * FROM users WHERE id=2').fetchone())
        rec=recommendations(db,user,2)
        assert rec and rec[0]['path_plan']['budget']==minutes
        assert sum(r['estimated_minutes'] for r in rec if r['in_current_plan'])<=minutes
        assert len({r['estimated_minutes'] for r in rec})>=2


def test_plan_opens_exact_question_and_completes_from_attempt(full):
    with get_db() as db:q=dict(db.execute("SELECT * FROM questions WHERE course_id=2 AND type='single' LIMIT 1").fetchone());user=dict(db.execute('SELECT * FROM users WHERE id=2').fetchone())
    plan=create_plan(PlanBody(course_id=2,title='完成指定题',knowledge_id=q['knowledge_id'],target={'question_id':q['id']}),user)
    assert f'question={q["id"]}' in plan['href']
    with get_db() as db:record_attempt(db,user,q,json.loads(q['answer']),include_recommendations=False)
    saved=next(p for p in plans(2,user) if p['id']==plan['id'])
    assert saved['status']=='completed' and saved['completion_source']=='event'


def test_classloop_uses_weak_knowledge_before_general_skill():
    students=[{'id':1,'features':[0,.9,0,0,0,0],'weak_knowledge_ids':[8]},{'id':2,'features':[0,.8,0,0,0,0],'weak_knowledge_ids':[8]}]
    questions=[{'id':1,'knowledge_id':2,'skill':'procedure','difficulty':2},{'id':2,'knowledge_id':8,'skill':'procedure','difficulty':2}]
    assert dynamic_groups(students,questions,1)[0]['question_ids'][0]==2


def test_short_activity_and_changed_duration_affect_path():
    states={i:estimate_state() for i in (1,2)}
    items=[{'knowledge_id':1,'estimated_minutes':3},{'knowledge_id':2,'estimated_minutes':9}]
    short=plan_path(items,{},states,3);assert short['knowledge_ids']==[1] and short['minutes']==3
    assert plan_path([items[0]|{'estimated_minutes':15},items[1]],{},states,10)['knowledge_ids']==[2]


def test_dia_verification_drives_persisted_workflow(full):
    from types import SimpleNamespace
    from backend.app.teaching_actions import prepare_actions
    from backend.app.teaching_agents import begin_collaboration,finalize_collaboration
    with get_db() as db:
        user=dict(db.execute('SELECT * FROM users WHERE id=2').fetchone())
        conv=db.execute("INSERT INTO ai_conversations(user_id,course_id,title) VALUES(2,2,'状态核对')").lastrowid
        kid=db.execute('SELECT id FROM knowledge_points WHERE course_id=2 ORDER BY id LIMIT 1').fetchone()[0]
        request=SimpleNamespace(course_id=2,knowledge_point_id=kid,question_id=None,resource_id=None)
        for variant,expected in [('valid','awaiting_check'),('empty','needs_revision'),('reference','partial'),('no_check','verified')]:
            plan=begin_collaboration(db,user,request,conv,prepare_actions(db,user,request,conv))
            if variant=='empty':plan['actions']=[]
            if variant=='no_check':plan['actions']=[a for a in plan['actions'] if a['kind']!='check']
            text,plan=finalize_collaboration(db,plan,'解释定义 [99]' if variant=='reference' else '解释定义与例子',[])
            status=db.execute('SELECT status FROM teaching_runs WHERE id=?',(plan['collaboration']['run_id'],)).fetchone()[0]
            assert status==expected
            assert plan['collaboration']['verification']['passed']==(variant in ('valid','no_check'))
            if variant in ('empty','no_check'):assert plan['check'] is None
            if variant=='valid':
                from backend.app.teaching_agents import record_feedback
                feedback=record_feedback(db,plan['check']['id'],{'correct':True,'id':1,'next_action':'review'})
                saved=db.execute('SELECT status,state FROM teaching_runs WHERE id=?',(plan['collaboration']['run_id'],)).fetchone()
                assert saved['status']==feedback['status']==json.loads(saved['state'])['status']=='feedback'


def test_assignment_plan_waits_for_all_graded_items(full):
    with get_db() as db:
        user=dict(db.execute('SELECT * FROM users WHERE id=2').fetchone())
        qs=[dict(r) for r in db.execute("SELECT * FROM questions WHERE course_id=2 AND type='single' AND status='approved' LIMIT 2")]
        assignment=db.execute("INSERT INTO assignments(course_id,teacher_id,title,question_ids) VALUES(2,1,'计划完成判据',?)",(json.dumps([q['id'] for q in qs]),)).lastrowid
    plan=create_plan(PlanBody(course_id=2,title='完成指定作业',kind='practice',target={'assignment_id':assignment}),user)
    with get_db() as db:record_attempt(db,user,qs[0],json.loads(qs[0]['answer']),assignment_id=assignment,include_recommendations=False)
    assert next(p for p in plans(2,user) if p['id']==plan['id'])['status']=='planned'
    with get_db() as db:record_attempt(db,user,qs[1],json.loads(qs[1]['answer']),assignment_id=assignment,include_recommendations=False)
    assert next(p for p in plans(2,user) if p['id']==plan['id'])['completion_source']=='event'
