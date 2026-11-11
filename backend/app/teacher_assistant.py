"""DIA-TEACH目标与班级证据双约束，受控工具、一次生成和草稿确认。"""
from __future__ import annotations

import json
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError

from .auth import current_user, require_teacher_course
from .db import get_db

router = APIRouter(prefix='/api/ai/teacher-drafts', tags=['教师教学草稿'])
TEACH_MARKER = '<!--XM_TEACH:'


class LessonStep(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    minutes: int = Field(ge=1, le=120)
    activity: str = Field(min_length=2, max_length=1000)


class GroupTask(BaseModel):
    group_id: str
    objective: str = Field(min_length=2, max_length=500)
    question_ids: list[int] = Field(min_length=1, max_length=8)


class TeachingDraft(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    objective: str = Field(min_length=2, max_length=1500)
    steps: list[LessonStep] = Field(min_length=1, max_length=8)
    groups: list[GroupTask] = Field(default_factory=list, max_length=4)


def prepare_teacher(db, user, request, conversation_id):
    require_teacher_course(db, user, request.course_id)
    from .routes_teaching import analytics_data
    message = request.message
    task = 'intervention' if any(term in message for term in ['分层','两组','后续练习']) else 'analysis' if any(term in message for term in ['学情','这个班','错误','掌握']) else 'design' if any(term in message for term in ['课','教案','安排','教学']) else 'discussion'
    matched = re.search(r'(\d{1,3})\s*分钟', message)
    minutes = min(120,max(5,int(matched.group(1)))) if matched else 40
    trace=[{'role':'教学任务规划','result':{'task':task,'minutes':minutes,'class_id':request.class_id}}]
    evidence={}
    if task in {'analysis','intervention','design'}:
        snapshot=analytics_data(db,user,request.course_id,request.class_id)
        points=[point for point in snapshot['knowledge'] if any(word in point['title'] for word in ['栈','队列'])] if any(word in message for word in ['栈','队列']) else snapshot['knowledge']
        point_ids={point['id'] for point in points}
        questions=[dict(row) for row in db.execute("SELECT id,knowledge_id,difficulty FROM questions WHERE course_id=? AND status='approved' AND type NOT IN ('short','step')",(request.course_id,)) if row['knowledge_id'] in point_ids]
        groups=[]
        for group in snapshot['groups']:
            weak={kid for student in snapshot['students'] if student['id'] in group['student_ids'] for kid in student['weak_knowledge_ids']}
            candidates=sorted(questions,key=lambda question:(question['knowledge_id'] not in weak,question['difficulty'],question['id']))[:3]
            if candidates:
                groups.append({key:group[key] for key in ['id','name','student_ids','focus','strategy']}|{'question_ids':[question['id'] for question in candidates],'knowledge_id':candidates[0]['knowledge_id']})
        evidence={'summary':snapshot['summary'],'errors':snapshot['error_distribution'],
            'knowledge':[{'id':point['id'],'title':point['title'],'observed_count':point['observed_count'],'average_mastery':point['average_mastery'],'distribution':point['distribution']} for point in points[:8]],
            'groups':groups,
            'assignments':[{'id':assignment['id'],'title':assignment['title'],'submission_count':assignment['submission_count']} for assignment in snapshot['assignments'][:5]],
            'generated_at':snapshot['generated_at']}
        trace.append({'role':'班级证据工具','result':{'tool':'analytics_data / CLASS-LOOP','student_count':snapshot['summary']['student_count'],'graded_attempts':snapshot['summary']['attempt_count']}})
    return {'method':'DIA-TEACH','task':task,'minutes':minutes,'evidence':evidence,'trace':trace,'conversation_id':conversation_id,'model_calls_limit':1}


def draft_sample(plan):
    groups=plan['evidence'].get('groups',[])[:2]
    return {'title':'状态追踪与边界讲评课','objective':'对照具体作答，区分操作顺序与结构边界，完成独立复测。',
        'steps':[{'title':'发现问题','minutes':5,'activity':'展示匿名错例，预测操作结果。'},
                 {'title':'对照实验','minutes':max(1,plan['minutes']-15),'activity':'用栈与队列的相同输入逐步追踪，并说明适用场景。'},
                 {'title':'独立练习与复测','minutes':10,'activity':'完成对应群组练习并记录错误步骤。'}],
        'groups':[{'group_id':group['id'],'objective':group['strategy'],'question_ids':group['question_ids'][:2]} for group in groups if group['question_ids']]}


def validate_draft(db, request, plan, payload):
    draft=TeachingDraft.model_validate(payload).model_dump()
    if sum(step['minutes'] for step in draft['steps']) > plan['minutes']:
        raise ValueError('教学安排超过课时预算')
    allowed={group['id']:group for group in plan['evidence'].get('groups',[])}
    for task in draft['groups']:
        if task['group_id'] not in allowed:
            raise ValueError('未知教学群组')
        group=allowed[task['group_id']]
        # 群组及候选题由统计工具提供，模型不能改写学生或跨课程对象。
        if not set(task['question_ids']) <= set(group['question_ids']):
            raise ValueError('任务题目超出当前群组候选')
        task['student_ids']=group['student_ids']
        task['name']=group['name']
        task['knowledge_id']=group['knowledge_id']
    return draft


def finalize_teacher(db,user,request,plan,content,citations):
    visible, _, raw=content.partition(TEACH_MARKER)
    artifact={}
    if plan['task'] in {'design','intervention'}:
        try:
            draft=validate_draft(db,request,plan,json.loads(raw.split('-->',1)[0]))
            key=f"{plan['conversation_id']}:{request.request_id}"
            db.execute('INSERT OR IGNORE INTO ai_teacher_drafts(user_id,course_id,conversation_id,kind,content,evidence,request_key) VALUES(?,?,?,?,?,?,?)',
                (user['id'],request.course_id,plan['conversation_id'],plan['task'],json.dumps(draft,ensure_ascii=False),json.dumps(plan['evidence'],ensure_ascii=False),key))
            row=db.execute('SELECT id FROM ai_teacher_drafts WHERE request_key=?',(key,)).fetchone()
            artifact={'id':row['id'],'kind':plan['task'],'draft':draft,'status':'draft'}
            plan['trace'].append({'role':'草稿质量校验','result':'课时、课程题目、群组与学生范围通过'})
        except (ValueError,ValidationError,TypeError,KeyError):
            plan['trace'].append({'role':'草稿质量校验','result':'结构未通过，请调整要求后重新生成'})
            artifact={'status':'invalid','error':'草稿结构或业务对象未通过校验'}
    from .retrieval import citation_support
    plan['citation_support']=citation_support(visible,citations)
    plan['status']='draft_ready' if artifact.get('id') else 'answered' if plan['task'] in {'analysis','discussion'} else 'needs_revision'
    return visible.strip(),plan,artifact


@router.get('/{draft_id}')
def detail(draft_id:int,user=Depends(current_user)):
    with get_db() as db:
        row=db.execute('SELECT * FROM ai_teacher_drafts WHERE id=? AND user_id=?',(draft_id,user['id'])).fetchone()
        if not row:
            raise HTTPException(404,'教学草稿不存在')
        require_teacher_course(db,user,row['course_id'])
        return dict(row)|{'content':json.loads(row['content']),'evidence':json.loads(row['evidence'])}


@router.post('/{draft_id}/save')
def save(draft_id:int,body:TeachingDraft,user=Depends(current_user)):
    from .retrieval import sync_index
    with get_db() as db:
        row=db.execute('SELECT * FROM ai_teacher_drafts WHERE id=? AND user_id=?',(draft_id,user['id'])).fetchone()
        if not row:
            raise HTTPException(404,'教学草稿不存在')
        require_teacher_course(db,user,row['course_id'])
        if row['saved_resource_id']:
            return {'resource_id':row['saved_resource_id'],'already_saved':True}
        old=json.loads(row['content'])
        minutes=sum(step['minutes'] for step in old['steps'])
        if sum(step.minutes for step in body.steps)>120:
            raise HTTPException(422,'教学安排超过120分钟')
        content='# '+body.title+'\n\n## 教学目标\n'+body.objective+'\n\n## 教学过程\n'+'\n\n'.join(f"### {step.title}（{step.minutes}分钟）\n{step.activity}" for step in body.steps)
        resource=db.execute("INSERT INTO resources(course_id,title,kind,content,metadata) VALUES(?,?,'lesson_plan',?,?)",(row['course_id'],body.title,content,json.dumps({'visibility':'teacher','status':'draft','source':'DIA-TEACH','draft_id':draft_id})))
        updated=body.model_dump()|{'groups':old['groups']}
        db.execute("UPDATE ai_teacher_drafts SET saved_resource_id=?,status='saved',content=? WHERE id=?",(resource.lastrowid,json.dumps(updated,ensure_ascii=False),draft_id))
        sync_index(db)
        return {'resource_id':resource.lastrowid,'already_saved':False}
