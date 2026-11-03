import json
import secrets
import sqlite3
from datetime import datetime,timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel,Field
from .db import get_db,json_fields
from .auth import current_user,teacher_user,require_course,require_teacher_course
from .learning import mastery_value,recommendations,record_attempt



def course_rows(db,user):
    where="c.teacher_id=?" if user["role"]=="teacher" else "EXISTS(SELECT 1 FROM classes cl JOIN class_members m ON m.class_id=cl.id WHERE cl.course_id=c.id AND m.student_id=?)"
    rows=db.execute(f"SELECT c.*,u.name teacher_name,(SELECT COUNT(*) FROM knowledge_points k WHERE k.course_id=c.id) knowledge_count FROM courses c JOIN users u ON c.teacher_id=u.id WHERE {where} ORDER BY c.id",(user["id"],)).fetchall()
    result=[]
    for row in rows:
        item=dict(row)
        if user["role"]=="teacher":
            val=db.execute("SELECT AVG(COALESCE(m.value,.2)) FROM knowledge_points k CROSS JOIN (SELECT DISTINCT cm.student_id FROM class_members cm JOIN classes cl ON cm.class_id=cl.id WHERE cl.course_id=?) students LEFT JOIN mastery m ON m.knowledge_id=k.id AND m.student_id=students.student_id WHERE k.course_id=?",(row["id"],row["id"])).fetchone()[0]
        else:
            val=db.execute("SELECT AVG(COALESCE(m.value,.2)) FROM knowledge_points k LEFT JOIN mastery m ON m.knowledge_id=k.id AND m.student_id=? WHERE k.course_id=?",(user["id"],row["id"])).fetchone()[0]
        item["progress"]=round((val or 0)*100)
        result.append(item)
    return result


def get_resource(row):
    return json_fields(row,["metadata"])


def public_question(row,user):
    item=json_fields(row,["options","answer","hints","rubric"])
    if user["role"]!="teacher":
        for key in ("answer","explanation"):
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


