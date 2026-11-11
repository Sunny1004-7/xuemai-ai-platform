"""学习安排的具体对象、跳转和事件完成判据。仅学习证据改变掌握度。"""
import json
from urllib.parse import urlencode
from fastapi import HTTPException

EXPERIMENTS = {'sort','tree','bfs','stack','queue','py-loop','py-branch','py-list','py-function'}


def validate_target(db, course_id, knowledge_id, kind, target):
    target = dict(target or {})
    for key, table in [('resource_id','resources'),('question_id','questions'),('assignment_id','assignments')]:
        if target.get(key):
            row = db.execute(f'SELECT * FROM {table} WHERE id=? AND course_id=?',(target[key],course_id)).fetchone()
            if not row:
                raise HTTPException(422,'学习对象不属于当前课程')
            if key == 'resource_id' and kind == 'video' and row['kind'] != 'video':
                raise HTTPException(422,'请选择视频资源')
    if target.get('experiment_id') and target['experiment_id'] not in EXPERIMENTS:
        raise HTTPException(422,'实验类型不存在')
    # 旧计划和手动新建安排可从所选知识点解析一个有效对象。
    if not any(target.get(k) for k in ('question_id','resource_id','assignment_id','experiment_id')) and knowledge_id:
        if kind in ('practice','review'):
            q=db.execute("SELECT id FROM questions WHERE course_id=? AND knowledge_id=? AND status='approved' ORDER BY difficulty,id LIMIT 1",(course_id,knowledge_id)).fetchone()
            if q: target['question_id']=q[0]
        elif kind in ('reading','video'):
            r=db.execute('SELECT id FROM resources WHERE course_id=? AND knowledge_id=? AND kind=? ORDER BY id LIMIT 1',(course_id,knowledge_id,'video' if kind=='video' else 'document')).fetchone()
            if r: target['resource_id']=r[0]
    target.setdefault('completion_kind', 'attempt' if kind in ('practice','review') else 'video_progress' if kind=='video' else 'experiment' if kind=='experiment' else 'self_report')
    target['video_timestamp']=max(0,min(86400,float(target.get('video_timestamp',0))))
    return target


def serialize_plan(db, row):
    item=dict(row)
    item['target']=json.loads(item.get('target') or '{}') if isinstance(item.get('target'),str) else item.get('target',{})
    query={'course':item['course_id'],'plan':item['id']}
    if item.get('knowledge_id'): query['knowledge']=item['knowledge_id']
    for key, param in [('resource_id','resource'),('question_id','question'),('assignment_id','assignment'),('experiment_id','mode'),('video_timestamp','t')]:
        if item['target'].get(key) is not None: query[param]=item['target'][key]
    route={'practice':'practice','review':'review','video':'video','reading':'resources','experiment':'experiments'}[item['kind']]
    item['href']='/'+route+'?'+urlencode(query)
    event=db.execute('SELECT kind,payload FROM learning_events WHERE id=?',(item.get('completion_event_id'),)).fetchone()
    item['completion_source']='self_report' if event and json.loads(event['payload']).get('self_reported') else 'event' if event else None
    return item


def complete_matching_plans(db, student_id, course_id, event_id, kind, payload):
    event=db.execute('SELECT created_at FROM learning_events WHERE id=?',(event_id,)).fetchone()
    for row in db.execute("SELECT * FROM study_plans WHERE student_id=? AND course_id=? AND status='planned' AND julianday(created_at)<=julianday(?)",(student_id,course_id,event[0])).fetchall():
        target=json.loads(row['target'])
        match=False
        if kind=='attempt' and target.get('assignment_id') and target['assignment_id']==payload.get('assignment_id'):
            task=db.execute('SELECT question_ids FROM assignments WHERE id=?',(target['assignment_id'],)).fetchone()
            questions=json.loads(task[0]) if task else []
            graded={r[0] for r in db.execute("SELECT DISTINCT question_id FROM attempts WHERE student_id=? AND assignment_id=? AND review_status!='pending_review'",(student_id,target['assignment_id']))}
            match=bool(questions) and set(questions)<=graded
        elif kind=='attempt' and target.get('question_id')==payload.get('question_id') and payload.get('review_status')!='pending_review':
            match=True
        elif kind=='video_progress' and target.get('resource_id')==payload.get('resource_id'):
            match=payload.get('watched_seconds',0)>=target.get('required_seconds',20)
        elif kind=='experiment' and target.get('experiment_id')==payload.get('mode'):
            match=payload.get('steps',0)>=3
        if match:
            db.execute("UPDATE study_plans SET status='completed',completion_event_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(event_id,row['id']))
