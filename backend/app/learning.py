"""Explainable evidence rules. Video exposure never equals independent mastery."""
import json
from fastapi import HTTPException


def mastery_value(db, student_id, knowledge_id):
    row=db.execute("SELECT value FROM mastery WHERE student_id=? AND knowledge_id=?",(student_id,knowledge_id)).fetchone()
    return float(row[0]) if row else .2


def recommendations(db,user,course_id):
    nodes=db.execute("SELECT * FROM knowledge_points WHERE course_id=? ORDER BY id",(course_id,)).fetchall()
    result=[]
    goals=db.execute("SELECT title,knowledge_ids FROM learning_goals WHERE student_id=? AND course_id=? AND status='active' ORDER BY id DESC",(user["id"],course_id)).fetchall()
    for node in nodes:
        value=mastery_value(db,user["id"],node["id"])
        wrong=db.execute("SELECT COUNT(*) FROM mistakes m JOIN questions q ON m.question_id=q.id WHERE m.student_id=? AND q.knowledge_id=? AND m.corrected=0",(user["id"],node["id"])).fetchone()[0]
        prereqs=db.execute("SELECT k.id,k.title FROM knowledge_edges e JOIN knowledge_points k ON e.source=k.id WHERE e.target=?",(node["id"],)).fetchall()
        weak=[p for p in prereqs if mastery_value(db,user["id"],p["id"])<.5]
        if value>=.85 and not wrong:
            continue
        video=db.execute("SELECT id FROM resources WHERE knowledge_id=? AND kind='video' ORDER BY id LIMIT 1",(node["id"],)).fetchone()
        kind="review" if wrong else ("video" if value<.45 and video else "practice")
        reason=(f"有 {wrong} 道未订正错题，先辨析错误再独立复测。" if wrong else f"当前掌握度 {round(value*100)}%，用{'片段学习后检查' if kind=='video' else '独立练习'}补充学习证据。")
        if weak:
            reason+="先修知识“"+weak[0]["title"]+"”尚需巩固。"
        related_goal=next((g for g in goals if node["id"] in json.loads(g["knowledge_ids"])),None)
        if related_goal:reason+="这也对应你的目标“"+related_goal["title"]+"”。"
        href=f"/review?knowledge={node['id']}" if wrong else f"/video?resource={video['id']}&knowledge={node['id']}" if kind=="video" else f"/practice?knowledge={node['id']}"
        result.append({"id":f"{kind}-{node['id']}","course_id":course_id,"knowledge_id":node["id"],"title":node["title"],"reason":reason,"kind":kind,"href":href,"priority":round((1-value)*100+wrong*30+len(weak)*8+(12 if related_goal else 0)),"mastery":round(value*100),"prerequisite_ids":[p["id"] for p in weak]})
    return sorted(result,key=lambda r:-r["priority"])


def normalize(answer):
    return str(answer).strip().casefold().replace(" ","").replace("（","(").replace("）",")")


def score_answer(question,answer):
    expected=json.loads(question["answer"])
    if question["type"] in ("short","step"):
        return None,0,"待教师复核","pending_review"
    if question["type"]=="multiple":
        actual=answer if isinstance(answer,list) else [answer]
        correct={normalize(a) for a in actual}=={normalize(a) for a in expected}
    else:
        correct=normalize(answer)==normalize(expected)
    return correct,100 if correct else 0,"" if correct else "概念混淆","automatic"


def record_attempt(db,user,question,answer,hints_used=0,assignment_id=None):
    if user["role"]!="student":
        raise HTTPException(403,"请使用学生账号提交作答")
    hints_used=max(0,min(int(hints_used),len(json.loads(question["hints"]))))
    correct,score,error_type,review_status=score_answer(question,answer)
    previous=db.execute("SELECT correct,created_at FROM attempts WHERE student_id=? AND question_id=? AND created_at>=datetime('now','-1 day') ORDER BY id DESC LIMIT 1",(user["id"],question["id"])).fetchone()
    cur=db.execute("INSERT INTO attempts(student_id,question_id,assignment_id,answer,correct,score,hints_used,error_type,review_status) VALUES(?,?,?,?,?,?,?,?,?)",(user["id"],question["id"],assignment_id,json.dumps(answer,ensure_ascii=False),None if correct is None else int(correct),score,hints_used,error_type,review_status))
    old=mastery_value(db,user["id"],question["knowledge_id"])
    value=old
    if correct is not None:
        # Immediate identical success is practice history, not new independent evidence.
        repeated_success=bool(correct and previous and previous["correct"]==1)
        delta=0 if repeated_success else (.18 if not hints_used else .07) if correct else -.14
        value=max(.05,min(.98,old+delta))
        level="transfer" if correct and not hints_used and question["difficulty"]>=3 else "independent" if correct and not hints_used else "assisted" if correct else "developing"
        db.execute("INSERT INTO mastery(student_id,knowledge_id,value,evidence_count,level) VALUES(?,?,?,1,?) ON CONFLICT(student_id,knowledge_id) DO UPDATE SET value=excluded.value,evidence_count=mastery.evidence_count+1,level=excluded.level,updated_at=CURRENT_TIMESTAMP",(user["id"],question["knowledge_id"],value,level))
        if not correct:
            db.execute("INSERT INTO mistakes(student_id,question_id,error_type,last_answer) VALUES(?,?,?,?) ON CONFLICT(student_id,question_id) DO UPDATE SET wrong_count=wrong_count+1,corrected=0,error_type=excluded.error_type,last_answer=excluded.last_answer,next_review_at=datetime('now','+1 day')",(user["id"],question["id"],error_type,json.dumps(answer,ensure_ascii=False)))
        else:
            db.execute("UPDATE mistakes SET corrected=1,next_review_at=datetime('now','+3 days'),last_answer=? WHERE student_id=? AND question_id=?",(json.dumps(answer,ensure_ascii=False),user["id"],question["id"]))
    payload={"attempt_id":cur.lastrowid,"question_id":question["id"],"correct":correct,"hints_used":hints_used,"review_status":review_status}
    db.execute("INSERT INTO learning_events(student_id,course_id,knowledge_id,kind,payload) VALUES(?,?,?,?,?)",(user["id"],question["course_id"],question["knowledge_id"],"attempt",json.dumps(payload)))
    return {"id":cur.lastrowid,"correct":correct,"score":score,"answer":json.loads(question["answer"]),"explanation":question["explanation"],"error_type":error_type,"mastery":round(value*100),"review_status":review_status,"rubric":json.loads(question["rubric"]),"recommendations":recommendations(db,user,question["course_id"])[:3]}
