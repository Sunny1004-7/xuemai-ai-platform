import json
import secrets
import sqlite3
from datetime import datetime,timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel,Field
from .db import get_db,json_fields
from .auth import current_user,teacher_user,require_course,require_teacher_course
from .learning import mastery_value,recommendations,record_attempt
from .evidence import knowledge_state,apply_evidence,diagnose_error



def course_rows(db,user):
    where="c.teacher_id=?" if user["role"]=="teacher" else "EXISTS(SELECT 1 FROM classes cl JOIN class_members m ON m.class_id=cl.id WHERE cl.course_id=c.id AND m.student_id=?)"
    rows=db.execute(f"SELECT c.*,u.name teacher_name,(SELECT COUNT(*) FROM knowledge_points k WHERE k.course_id=c.id) knowledge_count FROM courses c JOIN users u ON c.teacher_id=u.id WHERE {where} ORDER BY c.id",(user["id"],)).fetchall()
    result=[]
    for row in rows:
        item=dict(row)
        nodes=[r[0] for r in db.execute("SELECT id FROM knowledge_points WHERE course_id=?",(row["id"],))]
        students=[r[0] for r in db.execute("SELECT DISTINCT u.id FROM users u JOIN class_members m ON m.student_id=u.id JOIN classes cl ON cl.id=m.class_id WHERE cl.course_id=? AND u.active=1",(row["id"],))] if user["role"]=="teacher" else [user["id"]]
        values=[mastery_value(db,sid,kid) for sid in students for kid in nodes]
        item["progress"]=round(sum(values)/len(values)*100) if values else 0
        result.append(item)
    return result


def get_resource(row):
    return json_fields(row,["metadata"])


def public_question(row,user):
    item=json_fields(row,["options","answer","hints","rubric"])
    if user["role"]!="teacher":
        for key in ("answer","explanation","diagnostic_map"):
            item.pop(key,None)
    return item


def check_knowledge(db,course_id,knowledge_id):
    if knowledge_id is not None and not db.execute("SELECT 1 FROM knowledge_points WHERE id=? AND course_id=?",(knowledge_id,course_id)).fetchone():
        raise HTTPException(422,"知识点不属于当前课程")


def assignment_visible(db,user,row):
    require_course(db,user,row["course_id"])
    if user["role"]=="teacher": return True
    targets=json.loads(row["student_ids"])
    if targets and user["id"] not in targets: return False
    return not row["class_id"] or bool(db.execute("SELECT 1 FROM class_members WHERE class_id=? AND student_id=?",(row["class_id"],user["id"])).fetchone())


def assignment_item(db,user,row):
    item=json_fields(row,["question_ids","student_ids"])
    completed=db.execute("SELECT COUNT(DISTINCT question_id) FROM attempts WHERE assignment_id=? AND student_id=?",(row["id"],user["id"])).fetchone()[0]
    item["completed"]=completed>=len(item["question_ids"])
    item["completed_count"]=completed
    item["submission_count"]=db.execute("SELECT COUNT(DISTINCT student_id) FROM attempts WHERE assignment_id=?",(row["id"],)).fetchone()[0]
    return item




def save_assignment_baselines(db, assignment_id):
    row=db.execute("SELECT * FROM assignments WHERE id=?",(assignment_id,)).fetchone()
    kids=[r[0] for r in db.execute("SELECT DISTINCT knowledge_id FROM questions WHERE id IN (SELECT value FROM json_each(?))",(row['question_ids'],))]
    for student in db.execute("SELECT DISTINCT u.id FROM users u JOIN class_members m ON m.student_id=u.id JOIN classes c ON c.id=m.class_id WHERE c.course_id=? AND u.active=1",(row['course_id'],)):
        if not assignment_visible(db,dict(student)|{'role':'student'},row):continue
        for kid in kids:
            state=knowledge_state(db,student['id'],kid)
            db.execute("INSERT OR IGNORE INTO assignment_baselines VALUES(?,?,?,?,?)",(assignment_id,student['id'],kid,state['value'],state['effective_count']))


def intervention_comparison(db, assignment_id, student_id):
    result=[]
    for row in db.execute("SELECT b.*,k.title FROM assignment_baselines b JOIN knowledge_points k ON k.id=b.knowledge_id WHERE b.assignment_id=? AND b.student_id=?",(assignment_id,student_id)):
        state=knowledge_state(db,student_id,row['knowledge_id'])
        result.append({'knowledge_id':row['knowledge_id'],'title':row['title'],'baseline':round(row['value']*100,1),
                       'current':round(state['value']*100,1),'delta':round((state['value']-row['value'])*100,1),
                       'new_evidence':round(state['effective_count']-row['evidence_count'],2),'evidence':state})
    return result
