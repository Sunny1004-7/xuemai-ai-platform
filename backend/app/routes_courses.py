from .common import *

router=APIRouter(prefix="/api")

@router.get("/courses")
def courses(user=Depends(current_user)):
    with get_db() as db: return course_rows(db,user)


@router.get("/courses/{course_id}")
def course_detail(course_id:int,user=Depends(current_user)):
    with get_db() as db:
        item=require_course(db,user,course_id)
        item["chapters"]=[dict(r) for r in db.execute("SELECT * FROM chapters WHERE course_id=? ORDER BY position,id",(course_id,))]
        item["knowledge_points"]=[dict(r) for r in db.execute("SELECT * FROM knowledge_points WHERE course_id=?",(course_id,))]
        item["resources"]=[get_resource(r) for r in db.execute("SELECT * FROM resources WHERE course_id=?",(course_id,))]
        return item


@router.get("/courses/{course_id}/graph")
def graph(course_id:int,user=Depends(current_user)):
    with get_db() as db:
        require_course(db,user,course_id)
        nodes=[]
        for r in db.execute("SELECT * FROM knowledge_points WHERE course_id=? ORDER BY id",(course_id,)):
            item=dict(r)
            val=mastery_value(db,user["id"],r["id"])
            item.update(mastery=round(val*100),status="mastered" if val>=.75 else "developing" if val>=.5 else "weak",resource_count=db.execute("SELECT COUNT(*) FROM resources WHERE knowledge_id=?",(r["id"],)).fetchone()[0])
            nodes.append(item)
        return {"nodes":nodes,"edges":[dict(r) for r in db.execute("SELECT * FROM knowledge_edges WHERE course_id=?",(course_id,))]}


class CourseBody(BaseModel):
    title:str=Field(min_length=1,max_length=120)
    description:str=Field(default="",max_length=5000)
    code:str|None=Field(default=None,max_length=30)
    color:str="#42685b"


@router.post("/courses",status_code=201)
def create_course(body:CourseBody,user=Depends(teacher_user)):
    with get_db() as db:
        try:
            cur=db.execute("INSERT INTO courses(title,description,code,color,teacher_id) VALUES(?,?,?,?,?)",(body.title,body.description,body.code or secrets.token_hex(4).upper(),body.color,user["id"]))
        except sqlite3.IntegrityError:
            raise HTTPException(409,"课程代码已存在")
        return dict(db.execute("SELECT * FROM courses WHERE id=?",(cur.lastrowid,)).fetchone())


@router.patch("/courses/{course_id}")
def update_course(course_id:int,body:CourseBody,user=Depends(teacher_user)):
    with get_db() as db:
        old=require_teacher_course(db,user,course_id)
        db.execute("UPDATE courses SET title=?,description=?,code=?,color=? WHERE id=?",(body.title,body.description,body.code or old["code"],body.color,course_id))
        return {"id":course_id,"ok":True}


class TitleBody(BaseModel):
    title:str=Field(min_length=1,max_length=200)


@router.post("/courses/{course_id}/chapters",status_code=201)
def create_chapter(course_id:int,body:TitleBody,user=Depends(teacher_user)):
    with get_db() as db:
        require_teacher_course(db,user,course_id)
        position=db.execute("SELECT COALESCE(MAX(position),0)+1 FROM chapters WHERE course_id=?",(course_id,)).fetchone()[0]
        cur=db.execute("INSERT INTO chapters(course_id,title,position) VALUES(?,?,?)",(course_id,body.title,position))
        return {"id":cur.lastrowid,"title":body.title,"position":position}


class KnowledgeBody(BaseModel):
    title:str=Field(min_length=1,max_length=200)
    description:str=Field(default="",max_length=5000)
    chapter_id:int|None=None
    x:float=0
    y:float=0
    prerequisite_ids:list[int]=Field(default_factory=list,max_length=100)


def add_edge(db,course_id,source,target):
    check_knowledge(db,course_id,source)
    check_knowledge(db,course_id,target)
    if source==target:
        raise HTTPException(422,"知识点不能依赖自身")
    # A target already reaches source: insertion would create a cycle.
    cycle=db.execute("WITH RECURSIVE reachable(id) AS (SELECT target FROM knowledge_edges WHERE source=? UNION SELECT e.target FROM knowledge_edges e JOIN reachable r ON e.source=r.id) SELECT 1 FROM reachable WHERE id=?",(target,source)).fetchone()
    if cycle:
        raise HTTPException(422,"先修关系形成循环，请调整连线")
    try:
        cur=db.execute("INSERT INTO knowledge_edges(course_id,source,target) VALUES(?,?,?)",(course_id,source,target))
    except sqlite3.IntegrityError:
        raise HTTPException(409,"先修关系已存在")
    return {"id":cur.lastrowid,"source":source,"target":target}


@router.post("/courses/{course_id}/knowledge",status_code=201)
def create_knowledge(course_id:int,body:KnowledgeBody,user=Depends(teacher_user)):
    with get_db() as db:
        require_teacher_course(db,user,course_id)
        if body.chapter_id and not db.execute("SELECT 1 FROM chapters WHERE id=? AND course_id=?",(body.chapter_id,course_id)).fetchone():
            raise HTTPException(422,"章节不属于当前课程")
        cur=db.execute("INSERT INTO knowledge_points(course_id,chapter_id,title,description,x,y) VALUES(?,?,?,?,?,?)",(course_id,body.chapter_id,body.title,body.description,body.x,body.y))
        for source in body.prerequisite_ids: add_edge(db,course_id,source,cur.lastrowid)
        return dict(db.execute("SELECT * FROM knowledge_points WHERE id=?",(cur.lastrowid,)).fetchone())


@router.patch("/knowledge/{knowledge_id}")
def edit_knowledge(knowledge_id:int,body:KnowledgeBody,user=Depends(teacher_user)):
    with get_db() as db:
        row=db.execute("SELECT * FROM knowledge_points WHERE id=?",(knowledge_id,)).fetchone()
        if not row: raise HTTPException(404,"知识点不存在")
        require_teacher_course(db,user,row["course_id"])
        if body.chapter_id and not db.execute("SELECT 1 FROM chapters WHERE id=? AND course_id=?",(body.chapter_id,row["course_id"])).fetchone(): raise HTTPException(422,"章节不属于当前课程")
        db.execute("UPDATE knowledge_points SET title=?,description=?,chapter_id=?,x=?,y=? WHERE id=?",(body.title,body.description,body.chapter_id,body.x,body.y,knowledge_id))
        return {"id":knowledge_id,"ok":True}


@router.delete("/knowledge/{knowledge_id}")
def delete_knowledge(knowledge_id:int,user=Depends(teacher_user)):
    with get_db() as db:
        row=db.execute("SELECT * FROM knowledge_points WHERE id=?",(knowledge_id,)).fetchone()
        if not row: raise HTTPException(404,"知识点不存在")
        require_teacher_course(db,user,row["course_id"])
        db.execute("DELETE FROM knowledge_points WHERE id=?",(knowledge_id,))
        return {"ok":True}


class EdgeBody(BaseModel):
    source:int
    target:int


@router.post("/courses/{course_id}/edges",status_code=201)
def create_edge(course_id:int,body:EdgeBody,user=Depends(teacher_user)):
    with get_db() as db:
        require_teacher_course(db,user,course_id)
        return add_edge(db,course_id,body.source,body.target)


@router.delete("/edges/{edge_id}")
def delete_edge(edge_id:int,user=Depends(teacher_user)):
    with get_db() as db:
        row=db.execute("SELECT * FROM knowledge_edges WHERE id=?",(edge_id,)).fetchone()
        if not row: raise HTTPException(404,"关系不存在")
        require_teacher_course(db,user,row["course_id"])
        db.execute("DELETE FROM knowledge_edges WHERE id=?",(edge_id,))
        return {"ok":True}


