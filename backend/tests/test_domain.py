"""Offline business contracts: every test owns a temporary SQLite store."""
import json
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_db,init_db
from backend.app.auth import hash_password


@pytest.fixture()
def client(tmp_path,monkeypatch):
    monkeypatch.setenv("DATABASE_PATH",str(tmp_path/"domain.db"))
    monkeypatch.setenv("AI_MODE","mock")
    with TestClient(app) as api:yield api


def login(client,username="student1"):
    response=client.post("/api/auth/login",json={"username":username,"password":"Xuemai123!"})
    assert response.status_code==200,response.text
    return {"Authorization":"Bearer "+response.json()["token"]}


def test_auth_and_revocation(client):
    assert client.get("/api/courses").status_code==401
    assert client.post("/api/auth/login",json={"username":"student1","password":"wrong"}).status_code==401
    headers=login(client)
    assert client.get("/api/auth/me",headers=headers).json()["role"]=="student"
    assert client.post("/api/auth/logout",headers=headers).status_code==200
    assert client.get("/api/auth/me",headers=headers).status_code==401


def test_seed_is_idempotent(client):
    init_db();init_db()
    with get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0]==3
        assert db.execute("SELECT COUNT(*) FROM knowledge_points WHERE course_id=1").fetchone()[0]==8
        assert db.execute("PRAGMA foreign_keys").fetchone()[0]==1
    headers=login(client)
    assert len(client.get("/api/courses",headers=headers).json())==2


def test_roles_and_answer_privacy(client):
    student=login(client)
    questions=client.get("/api/questions",headers=student).json()
    assert "answer" not in questions[0] and "explanation" not in questions[0]
    assert client.get("/api/analytics",headers=student).status_code==403
    assert client.post("/api/courses",headers=student,json={"title":"越权"}).status_code==403
    teacher=login(client,"teacher")
    assert "answer" in client.get("/api/questions",headers=teacher).json()[0]


def test_course_lifecycle_and_join(client):
    teacher=login(client,"teacher");student=login(client)
    course=client.post("/api/courses",headers=teacher,json={"title":"新课程","description":"实际创建"}).json()
    cid=course["id"]
    assert client.get(f"/api/courses/{cid}",headers=student).status_code==403
    chapter=client.post(f"/api/courses/{cid}/chapters",headers=teacher,json={"title":"新章节"}).json()
    node=client.post(f"/api/courses/{cid}/knowledge",headers=teacher,json={"title":"新知识","chapter_id":chapter["id"]}).json()
    assert node["course_id"]==cid
    group=client.post("/api/classes",headers=teacher,json={"course_id":cid,"name":"新班级"}).json()
    assert client.post("/api/classes/join",headers=student,json={"join_code":group["join_code"]}).status_code==200
    assert client.get(f"/api/courses/{cid}",headers=student).json()["chapters"][0]["id"]==chapter["id"]


def test_graph_cycle_and_course_relation_validation(client):
    teacher=login(client,"teacher")
    response=client.post("/api/courses/1/edges",headers=teacher,json={"source":8,"target":1})
    assert response.status_code==422
    assert "循环" in response.json()["detail"]
    assert client.post("/api/courses/1/edges",headers=teacher,json={"source":9,"target":1}).status_code==422
    assert client.post("/api/courses/1/knowledge",headers=teacher,json={"title":"跨课程","chapter_id":4}).status_code==422
    assert len(client.get("/api/courses/1/graph",headers=teacher).json()["edges"])==8


def test_objective_grading_and_recommendation_change(client):
    student=login(client)
    before=client.get("/api/courses/1/graph",headers=student).json()["nodes"][1]["mastery"]
    result=client.post("/api/attempts",headers=student,json={"question_id":1,"answer":"3"}).json()
    assert result["correct"] is True and result["score"]==100
    assert result["mastery"]>before
    assert result["recommendations"] and "reason" in result["recommendations"][0]
    history=client.get("/api/attempts",headers=student).json()
    assert history[0]["answer"]=="3"


@pytest.mark.parametrize("qid,answer,correct",[(2,["撤销操作","函数调用","括号匹配"],True),(2,["函数调用"],False),(4,"正确",True),(5,"有序",True),(8,"O(1)",True)])
def test_multiple_types_deterministic(client,qid,answer,correct):
    response=client.post("/api/attempts",headers=login(client),json={"question_id":qid,"answer":answer})
    assert response.status_code==201,response.text
    assert response.json()["correct"] is correct


def test_short_answer_pending_review(client):
    result=client.post("/api/attempts",headers=login(client),json={"question_id":6,"answer":"枢轴过于极端，使用随机化"}).json()
    assert result["correct"] is None and result["review_status"]=="pending_review"
    assert result["rubric"]["total"]==100


def test_teacher_review_changes_analysis_once(client):
    student=login(client);teacher=login(client,"teacher")
    item=client.post("/api/attempts",headers=student,json={"question_id":6,"answer":"随机化枢轴避免持续不均衡划分"}).json()
    assert client.patch(f"/api/attempts/{item['id']}/review",headers=student,json={"score":90,"feedback":"越权"}).status_code==403
    reviewed=client.patch(f"/api/attempts/{item['id']}/review",headers=teacher,json={"score":90,"feedback":"原因和改进思路准确"})
    assert reviewed.status_code==200 and reviewed.json()["review_status"]=="teacher_reviewed"
    assert client.patch(f"/api/attempts/{item['id']}/review",headers=teacher,json={"score":90,"feedback":"重复"}).status_code==409
    assert any(a["id"]==item["id"] and a["student_name"]=="陈星河" for a in client.get("/api/attempts",headers=teacher).json())


def test_wrong_answer_correction_and_hint_penalty(client):
    student=login(client)
    wrong=client.post("/api/attempts",headers=student,json={"question_id":3,"answer":"最小元素"}).json()
    assert wrong["correct"] is False
    mistakes=client.get("/api/mistakes",headers=student).json()
    assert any(m["question_id"]==3 and not m["corrected"] for m in mistakes)
    corrected=client.post("/api/mistakes/3/review",headers=student,json={"answer":"最大元素","hints_used":1}).json()
    assert corrected["correct"] and corrected["mastery"]-wrong["mastery"]==7
    assert next(m for m in client.get("/api/mistakes",headers=student).json() if m["question_id"]==3)["corrected"]==1


def test_repeated_success_does_not_inflate_mastery(client):
    student=login(client)
    first=client.post("/api/attempts",headers=student,json={"question_id":3,"answer":"最大元素"}).json()
    second=client.post("/api/attempts",headers=student,json={"question_id":3,"answer":"最大元素"}).json()
    assert first["mastery"]==second["mastery"]


def test_private_video_requires_course_authorization(client):
    teacher=login(client,"teacher");student=login(client)
    uploaded=client.post("/api/resources/upload",headers=teacher,data={"course_id":"1","title":"私有教学视频","knowledge_id":"6"},files={"file":("test.mp4",b"private-video-content","video/mp4")})
    assert uploaded.status_code==201,uploaded.text
    url=uploaded.json()["url"]
    assert url.startswith("/api/resources/")
    assert client.get(url).status_code==401
    assert client.get(url,headers=student).content==b"private-video-content"
    with get_db() as db:db.execute("DELETE FROM class_members WHERE class_id=1 AND student_id=2")
    assert client.get(url,headers=student).status_code==403


@pytest.mark.parametrize("metadata",[{"checkpoints":"invalid"},{"checkpoints":[None]},{"timeline":[{"time":0,"knowledge_id":9}]},{"checkpoint_question_id":9},{"duration":30,"subtitles":[{"start":20,"end":10}]},{"duration":30,"checkpoints":[{"time":31,"question_id":3}]}])
def test_video_metadata_rejects_malformed_or_cross_course(client,metadata):
    teacher=login(client,"teacher")
    response=client.post("/api/resources",headers=teacher,json={"course_id":1,"title":"视频元数据校验","kind":"video","metadata":metadata})
    assert response.status_code==422,response.text


def test_assignment_teacher_student_loop(client):
    teacher=login(client,"teacher");student=login(client)
    task=client.post("/api/assignments",headers=teacher,json={"course_id":1,"title":"真实发布","class_id":1,"question_ids":[1,3]}).json()
    assert task["title"]=="真实发布"
    assert any(a["id"]==task["id"] for a in client.get("/api/assignments",headers=student).json())
    for qid,answer in [(1,"3"),(3,"最大元素")]:
        assert client.post("/api/attempts",headers=student,json={"question_id":qid,"answer":answer,"assignment_id":task["id"]}).status_code==201
    result=client.get(f"/api/assignments/{task['id']}/results",headers=teacher).json()
    assert result[0]["completed"] and result[0]["score"]==100
    assert client.get(f"/api/assignments/{task['id']}",headers=student).json()["completed"]


def test_targeted_assignment_and_new_analysis(client):
    teacher=login(client,"teacher");student=login(client);other=login(client,"student2")
    analysis=client.get("/api/analytics",headers=teacher).json()
    weak=next(n for n in analysis["knowledge"] if n["id"]==2)["weak_students"]
    assert any(s["id"]==2 for s in weak)
    task=client.post("/api/assignments",headers=teacher,json={"course_id":1,"title":"栈概念分层巩固","knowledge_id":2,"student_ids":[2],"question_ids":[1]}).json()
    assert client.get(f"/api/assignments/{task['id']}",headers=other).status_code==403
    client.post("/api/attempts",headers=student,json={"question_id":1,"answer":"3","assignment_id":task["id"]})
    after=client.get("/api/analytics",headers=teacher).json()
    assert after["summary"]["attempt_count"]==analysis["summary"]["attempt_count"]+1
    assert next(n for n in after["knowledge"] if n["id"]==2)["average_mastery"]>next(n for n in analysis["knowledge"] if n["id"]==2)["average_mastery"]


def test_assignment_cross_course_rejected(client):
    teacher=login(client,"teacher")
    assert client.post("/api/assignments",headers=teacher,json={"course_id":1,"title":"跨课","question_ids":[9]}).status_code==422
    assert client.post("/api/assignments",headers=teacher,json={"course_id":1,"title":"跨班","class_id":2,"question_ids":[1]}).status_code==422
    student=login(client)
    assert client.post("/api/attempts",headers=student,json={"question_id":8,"answer":"O(1)","assignment_id":1}).status_code==422


def test_video_event_and_notes_persist_without_fake_mastery(client):
    student=login(client)
    before=client.get("/api/courses/1/graph",headers=student).json()["nodes"][5]["mastery"]
    assert client.post("/api/events",headers=student,json={"course_id":1,"knowledge_id":6,"kind":"video_progress","payload":{"resource_id":100,"current_time":12}}).status_code==201
    after=client.get("/api/courses/1/graph",headers=student).json()["nodes"][5]["mastery"]
    assert before==after
    video=next(r for r in client.get("/api/resources",headers=student).json() if r["id"]==100)
    assert video["metadata"]["resume_position"]==12
    note=client.post("/api/notes",headers=student,json={"course_id":1,"knowledge_id":6,"resource_id":100,"timestamp":12,"content":"最大元素逐次右移"}).json()
    assert client.get("/api/notes",headers=student).json()[0]["id"]==note["id"]
    assert client.get("/api/notes",headers=login(client,"student2")).json()==[]


def test_resource_versions_upload_and_scoping(client):
    teacher=login(client,"teacher")
    result=client.post("/api/resources/upload",headers=teacher,data={"course_id":"1","title":"UTF8讲义","knowledge_id":"2"},files={"file":("stack.md","栈遵循后进先出".encode(),"text/markdown")})
    assert result.status_code==201,result.text
    resource=result.json()
    edited=client.patch(f"/api/resources/{resource['id']}",headers=teacher,json={"course_id":1,"knowledge_id":2,"title":"更新讲义","kind":"document","content":"先检查栈是否为空"})
    assert edited.json()["version"]==2
    versions=client.get(f"/api/resources/{resource['id']}/versions",headers=teacher).json()
    assert versions[0]["content"]=="栈遵循后进先出"
    partial=client.patch(f"/api/resources/{resource['id']}",headers=teacher,json={"title":"部分更新"})
    assert partial.status_code==200 and partial.json()["content"]=="先检查栈是否为空"
    assert client.post("/api/resources",headers=teacher,json={"course_id":1,"knowledge_id":9,"title":"跨课","kind":"document"}).status_code==422
    assert client.post("/api/resources",headers=teacher,json={"course_id":1,"title":"危险链接","kind":"link","url":"javascript:alert(1)"}).status_code==422


def test_classroom_response_privacy_and_close(client):
    teacher=login(client,"teacher");student=login(client);other=login(client,"student2")
    task=client.post("/api/classroom",headers=teacher,json={"course_id":1,"title":"实时提问","prompt":"栈和队列有什么区别？"}).json()
    assert client.post(f"/api/classroom/{task['id']}/responses",headers=student,json={"answer":"后进先出与先进先出"}).status_code==200
    teacher_view=client.get("/api/classroom",headers=teacher).json()[0]
    other_view=client.get("/api/classroom",headers=other).json()[0]
    assert len(teacher_view["responses"])==1 and len(other_view["responses"])==0
    client.patch(f"/api/classroom/{task['id']}",headers=teacher,json={"active":False})
    assert client.post(f"/api/classroom/{task['id']}/responses",headers=other,json={"answer":"关闭后不能答"}).status_code==409


def test_unrelated_teacher_cannot_read_or_mutate(client):
    with get_db() as db:db.execute("INSERT INTO users(id,username,name,role,password_hash) VALUES(4,'outsider','其他教师','teacher',?)",(hash_password("Xuemai123!"),))
    outsider=login(client,"outsider")
    assert client.get("/api/courses/1",headers=outsider).status_code==403
    assert client.get("/api/analytics?course_id=1",headers=outsider).status_code==403
    assert client.patch("/api/resources/1",headers=outsider,json={"course_id":1,"title":"越权","kind":"document"}).status_code==403
    assert client.get("/api/courses",headers=outsider).json()==[]


def test_dashboard_reports_actual_data(client):
    student=login(client);teacher=login(client,"teacher")
    dash=client.get("/api/dashboard",headers=student).json()
    assert dash["stats"]["courses"]==2 and dash["synthetic_data"]
    assert dash["recommendations"] and dash["assignments"]
    assert client.get("/api/dashboard",headers=teacher).json()["stats"]["students"]==2
