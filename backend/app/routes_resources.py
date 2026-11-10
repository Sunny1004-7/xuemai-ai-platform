from .common import *
import math
from pathlib import Path
from fastapi.responses import FileResponse
from .db import database_path
from .retrieval import sync_index

router=APIRouter(prefix="/api")

class ResourceBody(BaseModel):
    course_id:int
    title:str=Field(min_length=1,max_length=200)
    kind:str=Field(pattern="^(document|video|lesson_plan|experiment|link)$")
    content:str=Field(default="",max_length=300000)
    url:str=Field(default="",max_length=1000)
    knowledge_id:int|None=None
    metadata:dict=Field(default_factory=dict)


@router.get("/resources")
def resources(course_id:int=1,knowledge_id:int|None=None,q:str="",user=Depends(current_user)):
    with get_db() as db:
        require_course(db,user,course_id)
        query="SELECT * FROM resources WHERE course_id=?"; args=[course_id]
        if knowledge_id is not None: query+=" AND knowledge_id=?";args.append(knowledge_id)
        if q: query+=" AND (title LIKE ? OR content LIKE ?)";args.extend([f"%{q[:200]}%"]*2)
        result=[get_resource(r) for r in db.execute(query+" ORDER BY id",args)]
        latest={}
        for event in db.execute("SELECT payload FROM learning_events WHERE student_id=? AND course_id=? AND kind='video_progress' ORDER BY id DESC",(user["id"],course_id)):
            payload=json.loads(event[0]);rid=payload.get("resource_id")
            if isinstance(rid,int) and rid not in latest:
                value=payload.get("position",payload.get("current_time",0))
                if isinstance(value,(int,float)) and not isinstance(value,bool) and 0<=value<=86400:latest[rid]=value
        for item in result:
            if item["kind"]=="video":item["metadata"]["resume_position"]=latest.get(item["id"],0)
        return result


def validate_resource(db,body):
    check_knowledge(db,body.course_id,body.knowledge_id)
    import re
    if body.url and not (body.url.startswith("/media/") or body.url.startswith("https://") or re.fullmatch(r"/api/resources/\d+/file",body.url)):
        raise HTTPException(422,"资源链接只支持 HTTPS 或本地媒体")
    def number(value):
        return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and 0<=value<=86400
    duration=body.metadata.get("duration")
    if duration is not None and not number(duration):raise HTTPException(422,"视频时长须为0到86400秒之间的有限数值")
    for key in ("checkpoints","timeline","subtitles"):
        items=body.metadata.get(key,[])
        if not isinstance(items,list) or len(items)>1000:raise HTTPException(422,"时间轴、检查点和字幕必须是长度不超过1000的数组")
        for point in items:
            if not isinstance(point,dict):raise HTTPException(422,"时间轴条目必须是对象")
            for name in ("time","timestamp","start","end"):
                if name in point and (not number(point[name]) or duration is not None and point[name]>duration):raise HTTPException(422,"时间位置需在视频时长范围内")
            if "start" in point and "end" in point and point["end"]<point["start"]:raise HTTPException(422,"字幕结束时间不得早于开始时间")
            if point.get("knowledge_id") is not None:check_knowledge(db,body.course_id,point["knowledge_id"])
            if key=="checkpoints":
                qid=point.get("question_id")
                if not isinstance(qid,int) or not db.execute("SELECT 1 FROM questions WHERE id=? AND course_id=?",(qid,body.course_id)).fetchone():raise HTTPException(422,"检查题必须属于当前课程")
    qid=body.metadata.get("checkpoint_question_id")
    if qid is not None and (not isinstance(qid,int) or not db.execute("SELECT 1 FROM questions WHERE id=? AND course_id=?",(qid,body.course_id)).fetchone()):raise HTTPException(422,"检查题必须属于当前课程")


@router.post("/resources",status_code=201)
def create_resource(body:ResourceBody,user=Depends(teacher_user)):
    with get_db() as db:
        require_teacher_course(db,user,body.course_id)
        validate_resource(db,body)
        cur=db.execute("INSERT INTO resources(course_id,knowledge_id,title,kind,content,url,metadata) VALUES(?,?,?,?,?,?,?)",(body.course_id,body.knowledge_id,body.title,body.kind,body.content,body.url,json.dumps(body.metadata,ensure_ascii=False)))
        sync_index(db)
        return get_resource(db.execute("SELECT * FROM resources WHERE id=?",(cur.lastrowid,)).fetchone())


class ResourcePatch(BaseModel):
    course_id:int|None=None
    title:str|None=Field(default=None,min_length=1,max_length=200)
    kind:str|None=Field(default=None,pattern="^(document|video|lesson_plan|experiment|link)$")
    content:str|None=Field(default=None,max_length=300000)
    url:str|None=Field(default=None,max_length=1000)
    knowledge_id:int|None=None
    metadata:dict|None=None


@router.patch("/resources/{resource_id}")
def edit_resource(resource_id:int,body:ResourcePatch,user=Depends(teacher_user)):
    with get_db() as db:
        old=db.execute("SELECT * FROM resources WHERE id=?",(resource_id,)).fetchone()
        if not old: raise HTTPException(404,"资源不存在")
        require_teacher_course(db,user,old["course_id"])
        changes=body.model_dump(exclude_unset=True)
        if any(value is None and key!="knowledge_id" for key,value in changes.items()):raise HTTPException(422,"资源必填字段不能置空")
        body=ResourceBody(**(get_resource(old)|changes))
        if body.course_id!=old["course_id"]: raise HTTPException(422,"资源不可跨课程移动")
        validate_resource(db,body)
        db.execute("INSERT INTO resource_versions(resource_id,version,content,metadata) VALUES(?,?,?,?)",(resource_id,old["version"],old["content"],old["metadata"]))
        db.execute("UPDATE resources SET title=?,knowledge_id=?,kind=?,content=?,url=?,metadata=?,version=version+1 WHERE id=?",(body.title,body.knowledge_id,body.kind,body.content,body.url,json.dumps(body.metadata,ensure_ascii=False),resource_id))
        sync_index(db)
        return get_resource(db.execute("SELECT * FROM resources WHERE id=?",(resource_id,)).fetchone())


@router.get("/resources/{resource_id}/versions")
def resource_versions(resource_id:int,user=Depends(teacher_user)):
    with get_db() as db:
        old=db.execute("SELECT * FROM resources WHERE id=?",(resource_id,)).fetchone()
        if not old: raise HTTPException(404,"资源不存在")
        require_teacher_course(db,user,old["course_id"])
        return [json_fields(r,["metadata"]) for r in db.execute("SELECT * FROM resource_versions WHERE resource_id=? ORDER BY version DESC",(resource_id,))]


@router.delete("/resources/{resource_id}")
def delete_resource(resource_id:int,user=Depends(teacher_user)):
    with get_db() as db:
        row=db.execute("SELECT * FROM resources WHERE id=?",(resource_id,)).fetchone()
        if not row: raise HTTPException(404,"资源不存在")
        require_teacher_course(db,user,row["course_id"])
        db.execute("DELETE FROM resources WHERE id=?",(resource_id,))
        sync_index(db)
        return {"ok":True}


@router.post("/resources/upload",status_code=201)
async def upload_resource(course_id:int=Form(...),title:str=Form(...),knowledge_id:int|None=Form(None),file:UploadFile=File(...),user=Depends(teacher_user)):
    with get_db() as db: require_teacher_course(db,user,course_id);check_knowledge(db,course_id,knowledge_id)
    raw=await file.read(10*1024*1024+1)
    if len(raw)>10*1024*1024: raise HTTPException(413,"文件不能超过10MB")
    suffix=(file.filename or "").rsplit(".",1)[-1].lower()
    metadata={"filename":(file.filename or "资料")[:200]}
    url="";kind="document"
    if suffix=="pdf":
        from pypdf import PdfReader
        from io import BytesIO
        try:
            reader=PdfReader(BytesIO(raw))
            if len(reader.pages)>100:raise ValueError("too many pages")
            content="\n".join((page.extract_text() or "") for page in reader.pages)
            metadata["pages"]=len(reader.pages)
        except Exception: raise HTTPException(422,"PDF无法解析，请上传未加密、包含文本且不超过100页的PDF")
        if not content.strip(): raise HTTPException(422,"PDF没有可提取文字，请先进行OCR")
    elif suffix in ("txt","md","vtt","srt"):
        try:content=raw.decode("utf-8-sig")
        except UnicodeDecodeError:raise HTTPException(422,"文本资料请使用UTF-8编码")
    elif suffix in ("mp4","webm"):
        name=secrets.token_hex(16)+"."+suffix
        directory=database_path().parent/"uploads"
        directory.mkdir(parents=True,exist_ok=True)
        path=directory/name
        path.write_bytes(raw)
        kind="video";content="教师上传的视频"
    else:raise HTTPException(422,"支持 PDF、Markdown、TXT、字幕、MP4 与 WebM")
    try:
        result=create_resource(ResourceBody(course_id=course_id,title=title,kind=kind,content=content[:300000],url=url,knowledge_id=knowledge_id,metadata=metadata),user)
        if kind=="video":
            url=f"/api/resources/{result['id']}/file"
            with get_db() as db:
                db.execute("INSERT INTO resource_files(resource_id,filename,mime_type) VALUES(?,?,?)",(result["id"],name,"video/mp4" if suffix=="mp4" else "video/webm"))
                db.execute("UPDATE resources SET url=? WHERE id=?",(url,result["id"]))
            result["url"]=url
        return result
    except Exception:
        if kind=="video":path.unlink(missing_ok=True)
        raise


@router.get("/resources/{resource_id}/file")
def private_resource_file(resource_id:int,user=Depends(current_user)):
    with get_db() as db:
        row=db.execute("SELECT r.course_id,f.filename,f.mime_type FROM resources r JOIN resource_files f ON r.id=f.resource_id WHERE r.id=?",(resource_id,)).fetchone()
        if not row:raise HTTPException(404,"资源文件不存在")
        require_course(db,user,row["course_id"])
        name=row["filename"]
        if Path(name).name!=name:raise HTTPException(404,"资源文件不存在")
        path=database_path().parent/"uploads"/name
        if not path.is_file():raise HTTPException(404,"资源文件不存在")
        return FileResponse(path,media_type=row["mime_type"],headers={"Cache-Control":"private, no-store"})


