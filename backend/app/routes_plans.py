"""Student-owned goals and deliberate plans. Completion is not a mastery score."""
import json
from datetime import date
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from .auth import current_user,require_course
from .db import get_db,json_fields
from .common import check_knowledge
from .learning import recommendations
from .plan_targets import validate_target,serialize_plan

router=APIRouter(prefix="/api")


def student_user(user=Depends(current_user)):
    if user["role"]!="student":raise HTTPException(403,"个人学习目标与计划仅由学生本人管理")
    return user


def owned(db,table,item_id,user):
    if table not in ("learning_goals","study_plans"):raise ValueError("unknown entity")
    row=db.execute(f"SELECT * FROM {table} WHERE id=? AND student_id=?",(item_id,user["id"])).fetchone()
    if not row:raise HTTPException(404,"学习目标或计划不存在")
    require_course(db,user,row["course_id"])
    return row


class GoalBody(BaseModel):
    course_id:int
    title:str=Field(min_length=1,max_length=200)
    description:str=Field(default="",max_length=5000)
    target_date:date|None=None
    daily_minutes:int=Field(default=25,ge=5,le=240)
    knowledge_ids:list[int]=Field(default_factory=list,max_length=100)
    status:str=Field(default="active",pattern="^(active|completed|paused)$")


class GoalPatch(BaseModel):
    title:str|None=Field(default=None,min_length=1,max_length=200)
    description:str|None=Field(default=None,max_length=5000)
    target_date:date|None=None
    daily_minutes:int|None=Field(default=None,ge=5,le=240)
    knowledge_ids:list[int]|None=Field(default=None,max_length=100)
    status:str|None=Field(default=None,pattern="^(active|completed|paused)$")


def validate_goal(db,body):
    body.knowledge_ids=list(dict.fromkeys(body.knowledge_ids))
    for kid in body.knowledge_ids:check_knowledge(db,body.course_id,kid)


@router.get("/goals")
def goals(course_id:int=1,user=Depends(student_user)):
    with get_db() as db:
        require_course(db,user,course_id)
        return [json_fields(r,["knowledge_ids"]) for r in db.execute("SELECT * FROM learning_goals WHERE student_id=? AND course_id=? ORDER BY id DESC",(user["id"],course_id))]


@router.post("/goals",status_code=201)
def create_goal(body:GoalBody,user=Depends(student_user)):
    with get_db() as db:
        require_course(db,user,body.course_id);validate_goal(db,body)
        cur=db.execute("INSERT INTO learning_goals(student_id,course_id,title,description,target_date,daily_minutes,knowledge_ids,status) VALUES(?,?,?,?,?,?,?,?)",(user["id"],body.course_id,body.title,body.description,body.target_date.isoformat() if body.target_date else None,body.daily_minutes,json.dumps(body.knowledge_ids),body.status))
        return json_fields(db.execute("SELECT * FROM learning_goals WHERE id=?",(cur.lastrowid,)).fetchone(),["knowledge_ids"])


@router.patch("/goals/{goal_id}")
def edit_goal(goal_id:int,body:GoalPatch,user=Depends(student_user)):
    with get_db() as db:
        old=owned(db,"learning_goals",goal_id,user)
        changes=body.model_dump(exclude_unset=True)
        if any(v is None and k!="target_date" for k,v in changes.items()):raise HTTPException(422,"目标必填字段不能置空")
        updated=GoalBody(**(json_fields(old,["knowledge_ids"])|changes))
        validate_goal(db,updated)
        db.execute("UPDATE learning_goals SET title=?,description=?,target_date=?,daily_minutes=?,knowledge_ids=?,status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(updated.title,updated.description,updated.target_date.isoformat() if updated.target_date else None,updated.daily_minutes,json.dumps(updated.knowledge_ids),updated.status,goal_id))
        return json_fields(db.execute("SELECT * FROM learning_goals WHERE id=?",(goal_id,)).fetchone(),["knowledge_ids"])


@router.delete("/goals/{goal_id}")
def delete_goal(goal_id:int,user=Depends(student_user)):
    with get_db() as db:
        owned(db,"learning_goals",goal_id,user)
        db.execute("DELETE FROM learning_goals WHERE id=?",(goal_id,))
        return {"ok":True,"message":"目标已删除，已有计划保留"}


class PlanBody(BaseModel):
    course_id:int
    title:str=Field(min_length=1,max_length=200)
    description:str=Field(default="",max_length=5000)
    goal_id:int|None=None
    knowledge_id:int|None=None
    kind:str=Field(default="practice",pattern="^(practice|video|review|experiment|reading)$")
    scheduled_date:date|None=None
    estimated_minutes:int=Field(default=15,ge=1,le=240)
    status:str=Field(default="planned",pattern="^(planned|completed|skipped)$")
    target:dict=Field(default_factory=dict)


class PlanPatch(BaseModel):
    title:str|None=Field(default=None,min_length=1,max_length=200)
    description:str|None=Field(default=None,max_length=5000)
    goal_id:int|None=None
    knowledge_id:int|None=None
    kind:str|None=Field(default=None,pattern="^(practice|video|review|experiment|reading)$")
    scheduled_date:date|None=None
    estimated_minutes:int|None=Field(default=None,ge=1,le=240)
    status:str|None=Field(default=None,pattern="^(planned|completed|skipped)$")
    target:dict|None=None


def validate_plan(db,user,body):
    check_knowledge(db,body.course_id,body.knowledge_id)
    if body.goal_id:
        row=owned(db,"learning_goals",body.goal_id,user)
        if row["course_id"]!=body.course_id:raise HTTPException(422,"计划目标不属于当前课程")
    body.target=validate_target(db,body.course_id,body.knowledge_id,body.kind,body.target)


def plan_event(db,user,item_id,body):
    eid=db.execute("INSERT INTO learning_events(student_id,course_id,knowledge_id,kind,payload) VALUES(?,?,?,'plan_completed',?)",(user["id"],body.course_id,body.knowledge_id,json.dumps({"plan_id":item_id,"goal_id":body.goal_id,"self_reported":True,"affects_mastery":False}))).lastrowid
    db.execute('UPDATE study_plans SET completion_event_id=? WHERE id=?',(eid,item_id))


@router.get("/plans")
def plans(course_id:int=1,user=Depends(student_user)):
    with get_db() as db:
        require_course(db,user,course_id)
        return [serialize_plan(db,r) for r in db.execute("SELECT * FROM study_plans WHERE student_id=? AND course_id=? ORDER BY CASE status WHEN 'planned' THEN 0 ELSE 1 END,CASE WHEN status='planned' THEN scheduled_date END,CASE WHEN status!='planned' THEN updated_at END DESC,id DESC",(user["id"],course_id))]


@router.post("/plans",status_code=201)
def create_plan(body:PlanBody,user=Depends(student_user)):
    with get_db() as db:
        require_course(db,user,body.course_id);validate_plan(db,user,body)
        cur=db.execute("INSERT INTO study_plans(student_id,course_id,goal_id,knowledge_id,title,description,kind,scheduled_date,estimated_minutes,status) VALUES(?,?,?,?,?,?,?,?,?,?)",(user["id"],body.course_id,body.goal_id,body.knowledge_id,body.title,body.description,body.kind,body.scheduled_date.isoformat() if body.scheduled_date else None,body.estimated_minutes,body.status))
        db.execute('UPDATE study_plans SET target=? WHERE id=?',(json.dumps(body.target),cur.lastrowid))
        if body.status=="completed":plan_event(db,user,cur.lastrowid,body)
        return serialize_plan(db,db.execute("SELECT * FROM study_plans WHERE id=?",(cur.lastrowid,)).fetchone())


@router.patch("/plans/{plan_id}")
def edit_plan(plan_id:int,body:PlanPatch,user=Depends(student_user)):
    with get_db() as db:
        old=owned(db,"study_plans",plan_id,user)
        changes=body.model_dump(exclude_unset=True)
        if any(v is None and k not in ("knowledge_id","goal_id","scheduled_date") for k,v in changes.items()):raise HTTPException(422,"计划必填字段不能置空")
        updated=PlanBody(**(json_fields(old,['target'])|changes));validate_plan(db,user,updated)
        db.execute("UPDATE study_plans SET goal_id=?,knowledge_id=?,title=?,description=?,kind=?,scheduled_date=?,estimated_minutes=?,status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(updated.goal_id,updated.knowledge_id,updated.title,updated.description,updated.kind,updated.scheduled_date.isoformat() if updated.scheduled_date else None,updated.estimated_minutes,updated.status,plan_id))
        if old["status"]!="completed" and updated.status=="completed":plan_event(db,user,plan_id,updated)
        db.execute('UPDATE study_plans SET target=? WHERE id=?',(json.dumps(updated.target),plan_id))
        if updated.status!='completed':db.execute('UPDATE study_plans SET completion_event_id=NULL WHERE id=?',(plan_id,))
        return serialize_plan(db,db.execute("SELECT * FROM study_plans WHERE id=?",(plan_id,)).fetchone())


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id:int,user=Depends(student_user)):
    with get_db() as db:
        owned(db,"study_plans",plan_id,user)
        db.execute("DELETE FROM study_plans WHERE id=?",(plan_id,))
        return {"ok":True}


@router.get("/plan")
def personal_plan(course_id:int=1,user=Depends(student_user)):
    with get_db() as db:
        require_course(db,user,course_id)
        return {"goals":goals(course_id,user),"items":plans(course_id,user),"recommendations":recommendations(db,user,course_id),"explanation":"推荐基于作答证据与个人目标动态更新；勾选完成仅表示自报进度，不直接改变掌握度。"}
