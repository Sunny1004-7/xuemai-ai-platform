from .common import *

router=APIRouter(prefix="/api")

class ClassBody(BaseModel):
    course_id:int
    name:str=Field(min_length=1,max_length=100)


@router.get("/classes")
def classes(course_id:int|None=None,user=Depends(current_user)):
    with get_db() as db:
        allowed=[c["id"] for c in course_rows(db,user)]
        if course_id is not None: require_course(db,user,course_id);allowed=[course_id]
        result=[]
        for row in db.execute("SELECT * FROM classes"):
            if row["course_id"] not in allowed:continue
            if user["role"]=="student" and not db.execute("SELECT 1 FROM class_members WHERE class_id=? AND student_id=?",(row["id"],user["id"])).fetchone():continue
            item=dict(row)
            item["students"]=[dict(s) for s in db.execute("SELECT u.id,u.name,u.username FROM class_members m JOIN users u ON u.id=m.student_id WHERE m.class_id=? AND u.active=1",(row["id"],))] if user["role"]=="teacher" else []
            if user["role"]!="teacher":item.pop("join_code",None)
            result.append(item)
        return result


@router.post("/classes",status_code=201)
def create_class(body:ClassBody,user=Depends(teacher_user)):
    with get_db() as db:
        require_teacher_course(db,user,body.course_id)
        code=secrets.token_hex(3).upper()
        cur=db.execute("INSERT INTO classes(course_id,name,join_code) VALUES(?,?,?)",(body.course_id,body.name,code))
        return {"id":cur.lastrowid,"course_id":body.course_id,"name":body.name,"join_code":code,"students":[]}


class JoinBody(BaseModel):
    join_code:str=Field(min_length=1,max_length=30)


@router.post("/classes/join")
def join_class(body:JoinBody,user=Depends(current_user)):
    if user["role"]!="student":raise HTTPException(403,"仅学生可加入班级")
    with get_db() as db:
        row=db.execute("SELECT * FROM classes WHERE join_code=?",(body.join_code.upper(),)).fetchone()
        if not row:raise HTTPException(404,"班级邀请码不存在")
        db.execute("INSERT OR IGNORE INTO class_members VALUES(?,?)",(row["id"],user["id"]))
        return {"id":row["id"],"course_id":row["course_id"],"name":row["name"],"joined":True}


class MemberBody(BaseModel):
    student_id:int


@router.post("/classes/{class_id}/members")
def add_member(class_id:int,body:MemberBody,user=Depends(teacher_user)):
    with get_db() as db:
        row=db.execute("SELECT * FROM classes WHERE id=?",(class_id,)).fetchone()
        if not row:raise HTTPException(404,"班级不存在")
        require_teacher_course(db,user,row["course_id"])
        if not db.execute("SELECT 1 FROM users WHERE id=? AND role='student' AND active=1",(body.student_id,)).fetchone():raise HTTPException(422,"学生不存在")
        db.execute("INSERT OR IGNORE INTO class_members VALUES(?,?)",(class_id,body.student_id))
        return {"ok":True}


class ClassPatch(BaseModel):
    name:str=Field(min_length=1,max_length=100)


@router.patch("/classes/{class_id}")
def edit_class(class_id:int,body:ClassPatch,user=Depends(teacher_user)):
    with get_db() as db:
        row=db.execute("SELECT * FROM classes WHERE id=?",(class_id,)).fetchone()
        if not row:raise HTTPException(404,"班级不存在")
        require_teacher_course(db,user,row["course_id"])
        db.execute("UPDATE classes SET name=? WHERE id=?",(body.name,class_id))
        return dict(row)|{"name":body.name}


@router.delete("/classes/{class_id}")
def delete_class(class_id:int,user=Depends(teacher_user)):
    with get_db() as db:
        row=db.execute("SELECT * FROM classes WHERE id=?",(class_id,)).fetchone()
        if not row:raise HTTPException(404,"班级不存在")
        require_teacher_course(db,user,row["course_id"])
        if db.execute("SELECT 1 FROM assignments WHERE class_id=? LIMIT 1",(class_id,)).fetchone():raise HTTPException(409,"班级已有发布任务，删除会改变任务访问范围，请保留班级")
        db.execute("DELETE FROM classes WHERE id=?",(class_id,))
        return {"ok":True}


@router.delete("/classes/{class_id}/members/{student_id}")
def remove_member(class_id:int,student_id:int,user=Depends(teacher_user)):
    with get_db() as db:
        row=db.execute("SELECT * FROM classes WHERE id=?",(class_id,)).fetchone()
        if not row:raise HTTPException(404,"班级不存在")
        require_teacher_course(db,user,row["course_id"])
        cur=db.execute("DELETE FROM class_members WHERE class_id=? AND student_id=?",(class_id,student_id))
        if cur.rowcount==0:raise HTTPException(404,"该学生不在此班级")
        return {"ok":True}


def analytics_data(db,user,course_id,class_id=None):
    require_teacher_course(db,user,course_id)
    from .learning_insights import learning_snapshot, dynamic_groups
    if class_id is not None and not db.execute('SELECT 1 FROM classes WHERE id=? AND course_id=?',(class_id,course_id)).fetchone():
        raise HTTPException(422,'班级不属于当前课程')
    members=[r[0] for r in db.execute('SELECT DISTINCT u.id FROM users u JOIN class_members m ON m.student_id=u.id JOIN classes c ON c.id=m.class_id WHERE c.course_id=? AND u.active=1 AND (? IS NULL OR c.id=?)',(course_id,class_id,class_id))]
    result=learning_snapshot(db,course_id,members)
    questions=[dict(r) for r in db.execute("SELECT * FROM questions WHERE course_id=? AND status='approved' AND type NOT IN ('short','step')",(course_id,))]
    result['groups']=dynamic_groups(result['students'],questions)
    result['assignments']=[assignment_item(db,user,r) for r in db.execute("SELECT * FROM assignments WHERE course_id=? AND (? IS NULL OR class_id=? OR class_id IS NULL) ORDER BY id DESC",(course_id,class_id,class_id))]
    return result


@router.get('/analytics')
def analytics(course_id:int=1,class_id:int|None=None,user=Depends(teacher_user)):
    with get_db() as db:return analytics_data(db,user,course_id,class_id)


@router.get('/learning/insights')
def personal_insights(course_id:int=1,user=Depends(current_user)):
    if user['role']!='student':raise HTTPException(403,'请查看班级学情')
    from .learning_insights import learning_snapshot
    with get_db() as db:
        require_course(db,user,course_id)
        return learning_snapshot(db,course_id,[user['id']])


@router.get("/dashboard")
def dashboard(user=Depends(current_user)):
    with get_db() as db:
        courses=course_rows(db,user)
        course_ids=[c["id"] for c in courses]
        tasks=[assignment_item(db,user,r) for r in db.execute("SELECT * FROM assignments ORDER BY id DESC") if r["course_id"] in course_ids and assignment_visible(db,user,r)]
        query="SELECT e.*,k.title knowledge_title,u.name student_name FROM learning_events e LEFT JOIN knowledge_points k ON k.id=e.knowledge_id JOIN users u ON u.id=e.student_id WHERE e.student_id=? ORDER BY e.id DESC LIMIT 8"
        if user["role"]=="teacher":query="SELECT e.*,k.title knowledge_title,u.name student_name FROM learning_events e JOIN courses c ON c.id=e.course_id LEFT JOIN knowledge_points k ON k.id=e.knowledge_id JOIN users u ON u.id=e.student_id WHERE c.teacher_id=? ORDER BY e.id DESC LIMIT 8"
        recent=[json_fields(r,["payload"]) for r in db.execute(query,(user["id"],))]
        minutes=0
        for r in db.execute("SELECT payload FROM learning_events WHERE student_id=? AND kind='video_progress'",(user["id"],)):
            payload=json.loads(r[0])
            value=payload.get("watched_seconds",0)
            # Cumulative playback positions are not durations; malformed legacy entries are skipped.
            if isinstance(value,(float,int)) and not isinstance(value,bool) and 0<=value<=86400:minutes+=min(30,value)/60
        activity=[{"day":r[0],"count":r[1]} for r in db.execute("SELECT date(created_at),COUNT(*) FROM learning_events WHERE student_id=? AND created_at>=datetime('now','-7 days') GROUP BY date(created_at)",(user["id"],))]
        stats={"courses":len(courses),"study_minutes":round(minutes),"completed_tasks":sum(bool(t["completed"]) for t in tasks),"streak":len(activity),"mastery":round(sum(c["progress"] for c in courses)/len(courses)) if courses else 0,"students":0,"assignments":len(tasks)}
        recs=[]
        if user["role"]=="teacher":
            stats["students"]=db.execute("SELECT COUNT(DISTINCT m.student_id) FROM class_members m JOIN users u ON u.id=m.student_id AND u.active=1 JOIN classes cl ON cl.id=m.class_id JOIN courses c ON c.id=cl.course_id WHERE c.teacher_id=?",(user["id"],)).fetchone()[0]
            stats["mastery"]=round(sum(c["progress"] for c in courses)/len(courses)) if courses else 0
        else:
            for course in courses:recs.extend(recommendations(db,user,course["id"]))
        return {"user":user,"stats":stats,"courses":courses,"recommendations":sorted(recs,key=lambda r:-r["priority"])[:6],"assignments":tasks,"recent_events":recent,"weekly_activity":activity,"synthetic_data":True}


class ClassroomBody(BaseModel):
    course_id:int
    title:str=Field(min_length=1,max_length=200)
    prompt:str=Field(min_length=1,max_length=4000)
    kind:str=Field(default="question",pattern="^(question|quiz|feedback)$")


def classroom_item(db,row,user):
    item=dict(row)
    responses=db.execute("SELECT r.id,r.student_id,u.name,r.answer,r.created_at FROM classroom_responses r JOIN users u ON u.id=r.student_id WHERE r.activity_id=? ORDER BY r.id",(row["id"],)).fetchall()
    item["response_count"]=len(responses)
    item["responses"]=[dict(r) for r in responses if user["role"]=="teacher" or r["student_id"]==user["id"]]
    return item


@router.get("/classroom")
def classroom(course_id:int=1,user=Depends(current_user)):
    with get_db() as db:
        require_course(db,user,course_id)
        return [classroom_item(db,r,user) for r in db.execute("SELECT * FROM classroom WHERE course_id=? ORDER BY id DESC",(course_id,))]


@router.post("/classroom",status_code=201)
def create_classroom(body:ClassroomBody,user=Depends(teacher_user)):
    with get_db() as db:
        require_teacher_course(db,user,body.course_id)
        cur=db.execute("INSERT INTO classroom(course_id,title,prompt,kind) VALUES(?,?,?,?)",(body.course_id,body.title,body.prompt,body.kind))
        return classroom_item(db,db.execute("SELECT * FROM classroom WHERE id=?",(cur.lastrowid,)).fetchone(),user)


class ClassroomResponse(BaseModel):
    answer:str=Field(min_length=1,max_length=4000)


@router.post("/classroom/{activity_id}/responses")
def classroom_response(activity_id:int,body:ClassroomResponse,user=Depends(current_user)):
    if user["role"]!="student":raise HTTPException(403,"请使用学生账号参与课堂")
    with get_db() as db:
        row=db.execute("SELECT * FROM classroom WHERE id=?",(activity_id,)).fetchone()
        if not row:raise HTTPException(404,"课堂活动不存在")
        require_course(db,user,row["course_id"])
        if not row["active"]:raise HTTPException(409,"课堂活动已经结束")
        db.execute("INSERT INTO classroom_responses(activity_id,student_id,answer) VALUES(?,?,?) ON CONFLICT(activity_id,student_id) DO UPDATE SET answer=excluded.answer,created_at=CURRENT_TIMESTAMP",(activity_id,user["id"],body.answer))
        return {"ok":True}


class ClassroomEdit(BaseModel):
    active:bool


@router.patch("/classroom/{activity_id}")
def close_classroom(activity_id:int,body:ClassroomEdit,user=Depends(teacher_user)):
    with get_db() as db:
        row=db.execute("SELECT * FROM classroom WHERE id=?",(activity_id,)).fetchone()
        if not row:raise HTTPException(404,"课堂活动不存在")
        require_teacher_course(db,user,row["course_id"])
        db.execute("UPDATE classroom SET active=? WHERE id=?",(int(body.active),activity_id))
        return {"ok":True,"active":body.active}


@router.get('/analytics/evidence')
def student_evidence(course_id:int,student_id:int,knowledge_id:int,user=Depends(teacher_user)):
    with get_db() as db:
        require_teacher_course(db,user,course_id)
        check_knowledge(db,course_id,knowledge_id)
        member=db.execute("SELECT 1 FROM class_members m JOIN classes c ON c.id=m.class_id JOIN users u ON u.id=m.student_id WHERE m.student_id=? AND c.course_id=? AND u.active=1",(student_id,course_id)).fetchone()
        if not member:raise HTTPException(404,'学生不在本课程')
        rows=db.execute("SELECT e.*,q.title,a.answer,a.hints_used,a.review_status FROM evidence_updates e JOIN attempts a ON a.id=e.attempt_id JOIN questions q ON q.id=a.question_id WHERE e.student_id=? AND e.knowledge_id=? ORDER BY e.id DESC LIMIT 50",(student_id,knowledge_id))
        return {'state':knowledge_state(db,student_id,knowledge_id),'updates':[json_fields(r,['details','answer']) for r in rows]}
