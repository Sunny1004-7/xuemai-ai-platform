from .common import *

router=APIRouter(prefix="/api")

class EventBody(BaseModel):
    course_id:int
    knowledge_id:int|None=None
    kind:str=Field(pattern="^(video_progress|video_checkpoint|experiment|hint|understanding)$")
    payload:dict=Field(default_factory=dict)


@router.post("/events",status_code=201)
def event(body:EventBody,user=Depends(current_user)):
    with get_db() as db:
        require_course(db,user,body.course_id)
        check_knowledge(db,body.course_id,body.knowledge_id)
        if len(json.dumps(body.payload))>20000:raise HTTPException(422,"事件内容过长")
        rid=body.payload.get("resource_id")
        import math
        if rid is not None and (not isinstance(rid,int) or isinstance(rid,bool)):raise HTTPException(422,"资源编号必须是整数")
        for key in ("current_time","timestamp","watched_seconds","position"):
            if key in body.payload:
                value=body.payload[key]
                if not isinstance(value,(float,int)) or isinstance(value,bool) or not math.isfinite(value) or not 0<=value<=86400:raise HTTPException(422,"视频学习时间必须是0到86400秒之间的数值")
        if rid and not db.execute("SELECT 1 FROM resources WHERE id=? AND course_id=?",(rid,body.course_id)).fetchone():raise HTTPException(422,"资源不属于当前课程")
        cur=db.execute("INSERT INTO learning_events(student_id,course_id,knowledge_id,kind,payload) VALUES(?,?,?,?,?)",(user["id"],body.course_id,body.knowledge_id,body.kind,json.dumps(body.payload,ensure_ascii=False)))
        # Exposure is logged, not converted into a claimed independent success.
        if body.knowledge_id and user["role"]=="student":
            db.execute("INSERT OR IGNORE INTO mastery(student_id,knowledge_id,value,level) VALUES(?,?,.2,'exposed')",(user["id"],body.knowledge_id))
        return {"id":cur.lastrowid,"saved":True}


@router.get("/events")
def event_history(course_id:int=1,user=Depends(current_user)):
    with get_db() as db:
        require_course(db,user,course_id)
        return [json_fields(r,["payload"]) for r in db.execute("SELECT * FROM learning_events WHERE student_id=? AND course_id=? ORDER BY id DESC LIMIT 100",(user["id"],course_id))]


class NoteBody(BaseModel):
    course_id:int
    resource_id:int|None=None
    knowledge_id:int|None=None
    timestamp:float=Field(default=0,ge=0,le=100000)
    content:str=Field(min_length=1,max_length=8000)


@router.get("/notes")
def notes(course_id:int=1,resource_id:int|None=None,user=Depends(current_user)):
    with get_db() as db:
        require_course(db,user,course_id)
        query="SELECT * FROM notes WHERE student_id=? AND course_id=?";args=[user["id"],course_id]
        if resource_id is not None:query+=" AND resource_id=?";args.append(resource_id)
        return [dict(r) for r in db.execute(query+" ORDER BY id DESC",args)]


@router.post("/notes",status_code=201)
def create_note(body:NoteBody,user=Depends(current_user)):
    with get_db() as db:
        require_course(db,user,body.course_id);check_knowledge(db,body.course_id,body.knowledge_id)
        if body.resource_id and not db.execute("SELECT 1 FROM resources WHERE id=? AND course_id=?",(body.resource_id,body.course_id)).fetchone():raise HTTPException(422,"笔记资源不属于当前课程")
        cur=db.execute("INSERT INTO notes(student_id,course_id,resource_id,knowledge_id,timestamp,content) VALUES(?,?,?,?,?,?)",(user["id"],body.course_id,body.resource_id,body.knowledge_id,body.timestamp,body.content))
        return dict(db.execute("SELECT * FROM notes WHERE id=?",(cur.lastrowid,)).fetchone())


@router.delete("/notes/{note_id}")
def delete_note(note_id:int,user=Depends(current_user)):
    with get_db() as db:
        cur=db.execute("DELETE FROM notes WHERE id=? AND student_id=?",(note_id,user["id"]))
        if cur.rowcount==0:raise HTTPException(404,"笔记不存在")
        return {"ok":True}


