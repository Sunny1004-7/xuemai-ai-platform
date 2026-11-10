from .common import *

router=APIRouter(prefix="/api")

class QuestionBody(BaseModel):
    course_id:int
    knowledge_id:int
    type:str=Field(pattern="^(single|multiple|true_false|fill|short|step)$")
    title:str=Field(min_length=1,max_length=4000)
    options:list[str]=Field(default_factory=list,max_length=10)
    answer:str|list[str]
    explanation:str=Field(default="",max_length=6000)
    difficulty:int=Field(default=1,ge=1,le=3)
    hints:list[str]=Field(default_factory=list,max_length=6)
    rubric:dict=Field(default_factory=dict)
    status:str=Field(default="approved",pattern="^(draft|approved)$")


@router.get("/questions")
def questions(course_id:int=1,knowledge_id:int|None=None,type:str|None=None,difficulty:int|None=None,user=Depends(current_user)):
    with get_db() as db:
        require_course(db,user,course_id)
        query="SELECT * FROM questions WHERE course_id=?"
        args=[course_id]
        for key,val in (("knowledge_id",knowledge_id),("type",type),("difficulty",difficulty)):
            if val is not None: query+=f" AND {key}=?"; args.append(val)
        if user["role"]=="student": query+=" AND status='approved'"
        return [public_question(r,user) for r in db.execute(query+" ORDER BY id",args)]


@router.post("/questions",status_code=201)
def create_question(body:QuestionBody,user=Depends(teacher_user)):
    with get_db() as db:
        require_teacher_course(db,user,body.course_id)
        check_knowledge(db,body.course_id,body.knowledge_id)
        validate_question(body)
        cur=db.execute("INSERT INTO questions(course_id,knowledge_id,type,title,options,answer,explanation,difficulty,hints,rubric,status) VALUES(?,?,?,?,?,?,?,?,?,?,?)",question_values(body))
        return public_question(db.execute("SELECT * FROM questions WHERE id=?",(cur.lastrowid,)).fetchone(),user)


def validate_question(body):
    from .learning import normalize
    if any(not option.strip() for option in body.options) or len({normalize(o) for o in body.options})!=len(body.options):raise HTTPException(422,"题目选项必须非空且互不重复")
    if body.type in ("single","true_false") and (not isinstance(body.answer,str) or len(body.options)<2 or body.answer not in body.options):
        raise HTTPException(422,"选项题需至少两个选项，答案必须属于选项")
    if body.type=="true_false" and len(body.options)!=2:raise HTTPException(422,"判断题必须恰好包含两个选项")
    if body.type=="multiple" and (len(body.options)<2 or not isinstance(body.answer,list) or not body.answer or len(set(body.answer))!=len(body.answer) or not set(body.answer)<=set(body.options)):
        raise HTTPException(422,"多选题答案必须是非空的选项数组")
    if body.type in ("fill","short","step") and (not isinstance(body.answer,str) or not body.answer.strip()):raise HTTPException(422,"填空与主观题需要非空的参考答案")
    if body.type in ("short","step"):
        if not body.rubric:
            body.rubric={"criteria":[{"name":"核心概念与结论","points":40},{"name":"推理与步骤","points":40},{"name":"边界与表达","points":20}],"total":100}
        criteria=body.rubric.get("criteria")
        if not isinstance(criteria,list) or not criteria or any(not isinstance(c,dict) or not isinstance(c.get("name"),str) or not c["name"].strip() or not isinstance(c.get("points"),(int,float)) or isinstance(c.get("points"),bool) or not 0<c["points"]<=100 for c in criteria) or abs(sum(c["points"] for c in criteria)-100)>.001:raise HTTPException(422,"主观题量规需包含名称和分值，合计100分")
        body.rubric["total"]=100


def question_values(body):
    return (body.course_id,body.knowledge_id,body.type,body.title,json.dumps(body.options,ensure_ascii=False),json.dumps(body.answer,ensure_ascii=False),body.explanation,body.difficulty,json.dumps(body.hints,ensure_ascii=False),json.dumps(body.rubric,ensure_ascii=False),body.status)


class QuestionPatch(BaseModel):
    course_id:int|None=None
    knowledge_id:int|None=None
    type:str|None=Field(default=None,pattern="^(single|multiple|true_false|fill|short|step)$")
    title:str|None=Field(default=None,min_length=1,max_length=4000)
    options:list[str]|None=Field(default=None,max_length=10)
    answer:str|list[str]|None=None
    explanation:str|None=Field(default=None,max_length=6000)
    difficulty:int|None=Field(default=None,ge=1,le=3)
    hints:list[str]|None=Field(default=None,max_length=6)
    rubric:dict|None=None
    status:str|None=Field(default=None,pattern="^(draft|approved)$")


@router.patch("/questions/{question_id}")
def edit_question(question_id:int,body:QuestionPatch,user=Depends(teacher_user)):
    with get_db() as db:
        row=db.execute("SELECT * FROM questions WHERE id=?",(question_id,)).fetchone()
        if not row: raise HTTPException(404,"题目不存在")
        require_teacher_course(db,user,row["course_id"])
        changes=body.model_dump(exclude_unset=True)
        if any(v is None for v in changes.values()):raise HTTPException(422,"题目字段不能置空")
        body=QuestionBody(**(public_question(row,user)|changes))
        if body.course_id!=row["course_id"]:raise HTTPException(422,"题目不可跨课程移动，请在目标课程新建题目")
        require_teacher_course(db,user,body.course_id)
        check_knowledge(db,body.course_id,body.knowledge_id)
        validate_question(body)
        assigned=any(question_id in json.loads(a[0]) for a in db.execute("SELECT question_ids FROM assignments WHERE course_id=?",(body.course_id,)))
        attempted=bool(db.execute("SELECT 1 FROM attempts WHERE question_id=? LIMIT 1",(question_id,)).fetchone())
        if assigned or attempted:
            old=public_question(row,user)
            locked=("knowledge_id","type","options","answer")
            if any(getattr(body,k)!=old[k] for k in locked):raise HTTPException(409,"题目已有作业或学习记录，题型、答案和知识点请通过新建变式调整")
        if assigned and body.status!="approved":raise HTTPException(409,"题目已用于发布作业，不能撤回为草稿")
        db.execute("UPDATE questions SET course_id=?,knowledge_id=?,type=?,title=?,options=?,answer=?,explanation=?,difficulty=?,hints=?,rubric=?,status=? WHERE id=?",question_values(body)+(question_id,))
        return public_question(db.execute("SELECT * FROM questions WHERE id=?",(question_id,)).fetchone(),user)


@router.delete("/questions/{question_id}")
def delete_question(question_id:int,user=Depends(teacher_user)):
    with get_db() as db:
        row=db.execute("SELECT * FROM questions WHERE id=?",(question_id,)).fetchone()
        if not row: raise HTTPException(404,"题目不存在")
        require_teacher_course(db,user,row["course_id"])
        assigned=db.execute("SELECT question_ids FROM assignments WHERE course_id=?",(row["course_id"],)).fetchall()
        if any(question_id in json.loads(r[0]) for r in assigned): raise HTTPException(409,"题目已用于作业，请先调整作业")
        db.execute("DELETE FROM questions WHERE id=?",(question_id,))
        return {"ok":True}


class AttemptBody(BaseModel):
    question_id:int
    answer:str|list[str]=Field(max_length=8000)
    hints_used:int=Field(default=0,ge=0,le=10)
    assignment_id:int|None=None


@router.post("/attempts",status_code=201)
def attempt(body:AttemptBody,user=Depends(current_user)):
    with get_db() as db:
        question=db.execute("SELECT * FROM questions WHERE id=?",(body.question_id,)).fetchone()
        if not question: raise HTTPException(404,"题目不存在")
        require_course(db,user,question["course_id"])
        if question["status"]!="approved": raise HTTPException(403,"题目尚未审核")
        if body.assignment_id:
            task=db.execute("SELECT * FROM assignments WHERE id=?",(body.assignment_id,)).fetchone()
            if not task or not assignment_visible(db,user,task): raise HTTPException(403,"无权提交此任务")
            if task["course_id"]!=question["course_id"] or body.question_id not in json.loads(task["question_ids"]): raise HTTPException(422,"题目不属于此任务")
        return record_attempt(db,user,question,body.answer,body.hints_used,body.assignment_id)


@router.get("/attempts")
def attempt_history(course_id:int=1,user=Depends(current_user)):
    with get_db() as db:
        require_course(db,user,course_id)
        query="SELECT a.*,q.title,q.knowledge_id,q.type,q.rubric,u.name student_name FROM attempts a JOIN questions q ON a.question_id=q.id JOIN users u ON u.id=a.student_id WHERE q.course_id=?"
        args=[course_id]
        if user["role"]!="teacher":query+=" AND a.student_id=?";args.append(user["id"])
        return [json_fields(r,["answer","rubric"]) for r in db.execute(query+" ORDER BY a.id DESC LIMIT 100",args)]


class TeacherReviewBody(BaseModel):
    score:float=Field(ge=0,le=100)
    feedback:str=Field(min_length=1,max_length=6000)


@router.patch("/attempts/{attempt_id}/review")
def teacher_review(attempt_id:int,body:TeacherReviewBody,user=Depends(teacher_user)):
    with get_db() as db:
        row=db.execute("SELECT a.*,q.course_id,q.knowledge_id,q.type FROM attempts a JOIN questions q ON q.id=a.question_id WHERE a.id=?",(attempt_id,)).fetchone()
        if not row:raise HTTPException(404,"作答记录不存在")
        require_teacher_course(db,user,row["course_id"])
        if row["type"] not in ("short","step"):raise HTTPException(422,"此接口仅复核主观作答")
        if row["review_status"]=="teacher_reviewed":raise HTTPException(409,"此作答已经复核，避免重复修改学习证据")
        correct=body.score>=60
        db.execute("UPDATE attempts SET score=?,correct=?,review_status='teacher_reviewed',feedback=?,error_type=? WHERE id=?",(body.score,int(correct),body.feedback,"" if correct else "论证不充分",attempt_id))
        question=db.execute("SELECT * FROM questions WHERE id=?",(row['question_id'],)).fetchone()
        previous=db.execute("SELECT correct,created_at FROM attempts WHERE student_id=? AND question_id=? AND id<>? AND correct IS NOT NULL ORDER BY id DESC LIMIT 1",(row['student_id'],row['question_id'],attempt_id)).fetchone()
        update,schedule=apply_evidence(db,row['student_id'],question,attempt_id,correct,row['hints_used'],previous)
        value=update['value']
        if not correct:
            db.execute("INSERT INTO mistakes(student_id,question_id,error_type,last_answer) VALUES(?,?,'论证不充分',?) ON CONFLICT(student_id,question_id) DO UPDATE SET wrong_count=wrong_count+1,corrected=0,error_type='论证不充分',last_answer=excluded.last_answer",(row["student_id"],row["question_id"],row["answer"]))
        else:
            db.execute("UPDATE mistakes SET corrected=1,next_review_at=datetime('now','+3 days') WHERE student_id=? AND question_id=?",(row["student_id"],row["question_id"]))
        db.execute("INSERT INTO learning_events(student_id,course_id,knowledge_id,kind,payload) VALUES(?,?,?,'teacher_review',?)",(row["student_id"],row["course_id"],row["knowledge_id"],json.dumps({"attempt_id":attempt_id,"reviewer_id":user["id"],"score":body.score,"correct":correct})))
        return {"id":attempt_id,"score":body.score,"correct":correct,"review_status":"teacher_reviewed","feedback":body.feedback,"mastery":round(value*100)}


class AssignmentBody(BaseModel):
    course_id:int
    title:str=Field(min_length=1,max_length=200)
    question_ids:list[int]=Field(min_length=1,max_length=100)
    class_id:int|None=None
    student_ids:list[int]=Field(default_factory=list,max_length=1000)
    knowledge_id:int|None=None
    due_at:str|None=None
    description:str=Field(default="",max_length=5000)


@router.post("/assignments",status_code=201)
def create_assignment(body:AssignmentBody,user=Depends(teacher_user)):
    with get_db() as db:
        require_teacher_course(db,user,body.course_id)
        check_knowledge(db,body.course_id,body.knowledge_id)
        ids=list(dict.fromkeys(body.question_ids))
        for qid in ids:
            if not db.execute("SELECT 1 FROM questions WHERE id=? AND course_id=? AND status='approved'",(qid,body.course_id)).fetchone(): raise HTTPException(422,"作业题目需属于当前课程且已经审核")
        if body.class_id and not db.execute("SELECT 1 FROM classes WHERE id=? AND course_id=?",(body.class_id,body.course_id)).fetchone(): raise HTTPException(422,"班级不属于当前课程")
        for sid in body.student_ids:
            query="SELECT 1 FROM class_members m JOIN classes c ON c.id=m.class_id WHERE m.student_id=? AND c.course_id=?"
            if not db.execute(query,(sid,body.course_id)).fetchone(): raise HTTPException(422,"定向学生不属于当前课程")
            if body.class_id and not db.execute("SELECT 1 FROM class_members WHERE class_id=? AND student_id=?",(body.class_id,sid)).fetchone(): raise HTTPException(422,"定向学生不属于选定班级")
        cur=db.execute("INSERT INTO assignments(course_id,class_id,teacher_id,knowledge_id,title,description,question_ids,student_ids,due_at) VALUES(?,?,?,?,?,?,?,?,?)",(body.course_id,body.class_id,user["id"],body.knowledge_id,body.title,body.description,json.dumps(ids),json.dumps(body.student_ids),body.due_at))
        save_assignment_baselines(db,cur.lastrowid)
        return assignment_item(db,user,db.execute("SELECT * FROM assignments WHERE id=?",(cur.lastrowid,)).fetchone())


@router.get("/assignments")
def assignments(course_id:int|None=None,user=Depends(current_user)):
    with get_db() as db:
        courses=course_rows(db,user)
        allowed=[c["id"] for c in courses]
        if course_id is not None:
            require_course(db,user,course_id)
            allowed=[course_id]
        return [assignment_item(db,user,r) for r in db.execute("SELECT * FROM assignments ORDER BY id DESC") if r["course_id"] in allowed and assignment_visible(db,user,r)]


@router.get("/assignments/{assignment_id}")
def assignment_detail(assignment_id:int,user=Depends(current_user)):
    with get_db() as db:
        row=db.execute("SELECT * FROM assignments WHERE id=?",(assignment_id,)).fetchone()
        if not row: raise HTTPException(404,"作业不存在")
        if not assignment_visible(db,user,row): raise HTTPException(403,"无权访问此任务")
        item=assignment_item(db,user,row)
        item["questions"]=[public_question(db.execute("SELECT * FROM questions WHERE id=?",(qid,)).fetchone(),user) for qid in item["question_ids"]]
        return item


@router.get("/assignments/{assignment_id}/results")
def assignment_results(assignment_id:int,user=Depends(teacher_user)):
    with get_db() as db:
        row=db.execute("SELECT * FROM assignments WHERE id=?",(assignment_id,)).fetchone()
        if not row: raise HTTPException(404,"作业不存在")
        require_teacher_course(db,user,row["course_id"])
        result=[]
        ids=json.loads(row["question_ids"])
        for student in db.execute("SELECT DISTINCT u.id,u.name FROM users u JOIN class_members m ON u.id=m.student_id JOIN classes c ON c.id=m.class_id WHERE c.course_id=? AND u.active=1",(row["course_id"],)):
            if not assignment_visible(db,dict(student)|{"role":"student"},row):continue
            attempts=db.execute("SELECT a.* FROM attempts a WHERE assignment_id=? AND student_id=? AND a.id=(SELECT MAX(b.id) FROM attempts b WHERE b.assignment_id=a.assignment_id AND b.student_id=a.student_id AND b.question_id=a.question_id)",(assignment_id,student["id"])).fetchall()
            result.append(dict(student)|{"comparison":intervention_comparison(db,assignment_id,student["id"]),"interpretation":"任务完成与状态变化分别展示；状态对照不等同教学效果证实", "completed":len(attempts)>=len(ids),"completed_count":len(attempts),"score":round(sum(a["score"] for a in attempts)/len(ids),1),"attempts":[json_fields(a,["answer"]) for a in attempts]})
        return result


@router.get("/recommendations")
def get_recommendations(course_id:int=1,user=Depends(current_user)):
    with get_db() as db:
        require_course(db,user,course_id)
        return recommendations(db,user,course_id)


@router.get("/mistakes")
def mistakes(course_id:int=1,user=Depends(current_user)):
    with get_db() as db:
        require_course(db,user,course_id)
        query="""SELECT q.id question_id,q.title,q.course_id,q.knowledge_id,q.options,q.type,q.hints,q.difficulty,k.title knowledge_title,
                 COALESCE(m.error_type,'间隔复习') error_type,COALESCE(m.wrong_count,0) wrong_count,COALESCE(m.corrected,1) corrected,m.last_answer,
                 COALESCE(r.next_due,m.next_review_at) next_review_at,r.interval_days,r.ease,r.last_quality
                 FROM questions q JOIN knowledge_points k ON k.id=q.knowledge_id
                 LEFT JOIN mistakes m ON m.question_id=q.id AND m.student_id=?
                 LEFT JOIN review_schedule r ON r.question_id=q.id AND r.student_id=?
                 WHERE q.course_id=? AND (m.question_id IS NOT NULL OR r.question_id IS NOT NULL)
                 ORDER BY COALESCE(m.corrected,1),julianday(COALESCE(r.next_due,m.next_review_at))"""
        return [json_fields(r,["options","last_answer","hints"]) for r in db.execute(query,(user['id'],user['id'],course_id))]


class ReviewBody(BaseModel):
    answer:str|list[str]
    hints_used:int=Field(default=0,ge=0,le=10)


@router.post("/mistakes/{question_id}/review")
def review(question_id:int,body:ReviewBody,user=Depends(current_user)):
    return attempt(AttemptBody(question_id=question_id,answer=body.answer,hints_used=body.hints_used),user)




@router.get('/review-schedule')
def review_schedule(course_id:int=1,user=Depends(current_user)):
    with get_db() as db:
        require_course(db,user,course_id)
        return [dict(r) for r in db.execute("SELECT r.*,q.title,q.knowledge_id,k.title knowledge_title,julianday(r.next_due)<=julianday('now') due FROM review_schedule r JOIN questions q ON q.id=r.question_id JOIN knowledge_points k ON k.id=q.knowledge_id WHERE r.student_id=? AND q.course_id=? ORDER BY r.next_due",(user['id'],course_id))]
