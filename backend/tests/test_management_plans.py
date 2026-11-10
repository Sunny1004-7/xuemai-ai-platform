import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_db


@pytest.fixture()
def client(tmp_path,monkeypatch):
    monkeypatch.setenv("DATABASE_PATH",str(tmp_path/"management.db"))
    monkeypatch.setenv("AI_MODE","mock")
    with TestClient(app) as api:yield api


def login(client,name="student1"):
    if name=="student2":
        from backend.app.auth import hash_password
        with get_db() as db:
            if not db.execute("SELECT 1 FROM users WHERE username='student2'").fetchone():
                db.execute("INSERT INTO users(id,username,name,role,password_hash) VALUES(3,'student2','隔离测试学生','student',?)",(hash_password('Xuemai123!'),))
                db.executemany("INSERT OR IGNORE INTO class_members VALUES(?,3)",[(1,),(2,)])
    response=client.post("/api/auth/login",json={"username":name,"password":"Xuemai123!"})
    assert response.status_code==200
    return {"Authorization":"Bearer "+response.json()["token"]}


def test_chapter_objectives_persist_and_delete_preserves_knowledge(client):
    teacher=login(client,"teacher");student=login(client)
    chapter=client.post("/api/courses/1/chapters",headers=teacher,json={"title":"图算法拓展","objectives":["能手工执行BFS"]}).json()
    kid=client.post("/api/courses/1/knowledge",headers=teacher,json={"title":"图最短路拓展","chapter_id":chapter["id"],"objectives":["比较BFS和加权最短路"]}).json()["id"]
    assert client.patch(f"/api/chapters/{chapter['id']}",headers=student,json={"title":"越权"}).status_code==403
    updated=client.patch(f"/api/chapters/{chapter['id']}",headers=teacher,json={"objectives":["掌握无权最短路"],"position":6})
    assert updated.status_code==200
    reopened=client.get("/api/courses/1",headers=student).json()
    assert next(c for c in reopened["chapters"] if c["id"]==chapter["id"])["objectives"]==["掌握无权最短路"]
    assert client.delete(f"/api/chapters/{chapter['id']}",headers=teacher).status_code==200
    node=next(k for k in client.get("/api/courses/1/graph",headers=student).json()["nodes"] if k["id"]==kid)
    assert node["chapter_id"] is None and node["objectives"]==["比较BFS和加权最短路"]


def test_partial_knowledge_edit_preserves_fields_and_rejects_cycle_atomically(client):
    teacher=login(client,"teacher")
    before=client.get("/api/courses/1/graph",headers=teacher).json()
    edited=client.patch("/api/knowledge/2",headers=teacher,json={"objectives":["辨析先进先出与后进先出"],"x":320})
    assert edited.status_code==200 and edited.json()["title"]=="栈与队列" and edited.json()["x"]==320
    cycle=client.patch("/api/knowledge/1",headers=teacher,json={"title":"不应保存","prerequisite_ids":[8]})
    assert cycle.status_code==422
    after=client.get("/api/courses/1/graph",headers=teacher).json()
    assert after["nodes"][0]["title"]==before["nodes"][0]["title"]
    assert after["edges"]==before["edges"]


def test_course_patch_conflict_and_class_lifecycle(client):
    teacher=login(client,"teacher");student=login(client)
    assert client.patch("/api/courses/1",headers=teacher,json={"description":"课程描述独立更新"}).json()["title"]=="数据结构与算法"
    assert client.patch("/api/courses/1",headers=teacher,json={"code":"CS101"}).status_code==409
    group=client.post("/api/classes",headers=teacher,json={"course_id":1,"name":"课后小组"}).json()
    cid=group["id"]
    assert client.patch(f"/api/classes/{cid}",headers=teacher,json={"name":"算法学习小组"}).json()["name"]=="算法学习小组"
    assert client.post(f"/api/classes/{cid}/members",headers=teacher,json={"student_id":2}).status_code==200
    assert client.delete(f"/api/classes/{cid}/members/2",headers=student).status_code==403
    assert client.delete(f"/api/classes/{cid}/members/2",headers=teacher).status_code==200
    assert client.delete(f"/api/classes/{cid}",headers=teacher).status_code==200
    assert client.delete("/api/classes/1",headers=teacher).status_code==409
    assert client.get("/api/assignments/1",headers=student).status_code==200


def test_question_draft_review_edit_and_published_lock(client):
    teacher=login(client,"teacher");student=login(client)
    body={"course_id":1,"knowledge_id":2,"type":"single","title":"教师审核草稿","options":["先进先出","后进先出"],"answer":"后进先出","status":"draft"}
    item=client.post("/api/questions",headers=teacher,json=body).json()
    qid=item["id"]
    assert qid not in [q["id"] for q in client.get("/api/questions",headers=student).json()]
    assert client.post("/api/attempts",headers=student,json={"question_id":qid,"answer":"后进先出"}).status_code==403
    approved=client.patch(f"/api/questions/{qid}",headers=teacher,json={"status":"approved","title":"栈遵循哪一种访问顺序？"})
    assert approved.status_code==200 and approved.json()["status"]=="approved"
    assert qid in [q["id"] for q in client.get("/api/questions",headers=student).json()]
    client.post("/api/assignments",headers=teacher,json={"course_id":1,"title":"锁定题目版本","question_ids":[qid]})
    assert client.patch(f"/api/questions/{qid}",headers=teacher,json={"answer":"先进先出"}).status_code==409
    assert client.patch(f"/api/questions/{qid}",headers=teacher,json={"status":"draft"}).status_code==409
    assert client.patch(f"/api/questions/{qid}",headers=teacher,json={"explanation":"栈从同一端插入和删除。"}).status_code==200


@pytest.mark.parametrize("changes",[{"options":["A","A"],"answer":"A"},{"options":["","B"],"answer":"B"},{"type":"multiple","options":["A","B"],"answer":["A","A"]},{"type":"true_false","options":["A","B","C"],"answer":"A"},{"type":"fill","options":[],"answer":""},{"type":"short","answer":"说明","rubric":{"criteria":[{"name":"概念","points":70}]}}])
def test_question_semantic_validation(client,changes):
    teacher=login(client,"teacher")
    base={"course_id":1,"knowledge_id":2,"type":"single","title":"题目校验","options":["A","B"],"answer":"A"}
    response=client.post("/api/questions",headers=teacher,json=base|changes)
    assert response.status_code==422,response.text


def test_short_question_default_rubric_can_be_reviewed(client):
    teacher=login(client,"teacher");student=login(client)
    item=client.post("/api/questions",headers=teacher,json={"course_id":1,"knowledge_id":2,"type":"short","title":"解释队列的使用场景","answer":"队列可用于BFS"}).json()
    assert sum(c["points"] for c in item["rubric"]["criteria"])==100
    attempt=client.post("/api/attempts",headers=student,json={"question_id":item["id"],"answer":"排队处理请求"}).json()
    assert attempt["review_status"]=="pending_review"
    result=client.patch(f"/api/attempts/{attempt['id']}/review",headers=teacher,json={"score":80,"feedback":"说明了先进先出的应用"}).json()
    assert result["review_status"]=="teacher_reviewed"
    with get_db() as db:
        event=db.execute("SELECT payload FROM learning_events WHERE student_id=2 AND kind='teacher_review' ORDER BY id DESC LIMIT 1").fetchone()
        assert '"score": 80.0' in event[0]


def test_goal_edit_changes_recommendation_and_preserves_privacy(client):
    student=login(client);other=login(client,"student2");teacher=login(client,"teacher")
    goal=client.post("/api/goals",headers=student,json={"course_id":1,"title":"理解树的遍历","knowledge_ids":[4],"daily_minutes":30,"target_date":"2026-11-18"}).json()
    assert goal["daily_minutes"]==30
    rec=next(r for r in client.get("/api/recommendations",headers=student).json() if r["knowledge_id"]==4)
    assert "理解树的遍历" in rec["reason"]
    assert client.get("/api/goals",headers=other).json()==[]
    assert client.patch(f"/api/goals/{goal['id']}",headers=other,json={"title":"越权修改"}).status_code==404
    assert client.get("/api/goals",headers=teacher).status_code==403
    updated=client.patch(f"/api/goals/{goal['id']}",headers=student,json={"title":"自己能解释树遍历","status":"paused","target_date":None}).json()
    assert updated["title"]=="自己能解释树遍历" and updated["target_date"] is None
    rec=next(r for r in client.get("/api/recommendations",headers=student).json() if r["knowledge_id"]==4)
    assert "理解树的遍历" not in rec["reason"]


def test_plan_complete_is_owned_persistent_and_does_not_fake_mastery(client):
    student=login(client);other=login(client,"student2")
    goal=client.post("/api/goals",headers=student,json={"course_id":1,"title":"排序学习目标","knowledge_ids":[6]}).json()
    before=next(n for n in client.get("/api/courses/1/graph",headers=student).json()["nodes"] if n["id"]==6)["mastery"]
    item=client.post("/api/plans",headers=student,json={"course_id":1,"goal_id":goal["id"],"knowledge_id":6,"title":"看视频并记录疑问","kind":"video","scheduled_date":"2026-11-04"}).json()
    assert client.patch(f"/api/plans/{item['id']}",headers=other,json={"status":"completed"}).status_code==404
    assert client.patch(f"/api/plans/{item['id']}",headers=student,json={"status":"completed","estimated_minutes":20}).status_code==200
    assert client.get("/api/plan",headers=student).json()["items"][0]["status"]=="completed"
    after=next(n for n in client.get("/api/courses/1/graph",headers=student).json()["nodes"] if n["id"]==6)["mastery"]
    assert before==after
    assert client.delete(f"/api/goals/{goal['id']}",headers=student).status_code==200
    assert client.get("/api/plans",headers=student).json()[0]["goal_id"] is None
    assert client.delete(f"/api/plans/{item['id']}",headers=student).status_code==200


def test_goals_and_plans_reject_cross_course_relations(client):
    student=login(client)
    assert client.post("/api/goals",headers=student,json={"course_id":1,"title":"跨课知识点","knowledge_ids":[9]}).status_code==422
    goal=client.post("/api/goals",headers=student,json={"course_id":2,"title":"Python目标","knowledge_ids":[9]}).json()
    assert client.post("/api/plans",headers=student,json={"course_id":1,"title":"跨课目标","goal_id":goal["id"]}).status_code==422
    assert client.post("/api/goals",headers=student,json={"course_id":1,"title":"格式错误日期","target_date":"not-date"}).status_code==422
