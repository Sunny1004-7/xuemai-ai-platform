"""可解释学习路径：证据更新与复习调度由同一套模型驱动。"""
import json
from fastapi import HTTPException
from .evidence import knowledge_state, apply_evidence, diagnose_error, utc_now, estimate_state, parse_time
from .path_planner import order_recommendations


def mastery_value(db, student_id, knowledge_id):
    return knowledge_state(db, student_id, knowledge_id)['value']


def recommendations(db, user, course_id):
    nodes = [dict(r) for r in db.execute('SELECT * FROM knowledge_points WHERE course_id=? ORDER BY id', (course_id,))]
    stored = {r['knowledge_id']: r for r in db.execute('SELECT * FROM mastery WHERE student_id=?', (user['id'],))}
    states = {n['id']: estimate_state(stored.get(n['id'])) for n in nodes}
    wrongs = dict(db.execute('SELECT q.knowledge_id,COUNT(*) FROM mistakes m JOIN questions q ON q.id=m.question_id WHERE m.student_id=? AND m.corrected=0 GROUP BY q.knowledge_id', (user['id'],)))
    schedules = {}
    for row in db.execute('SELECT r.*,q.knowledge_id FROM review_schedule r JOIN questions q ON q.id=r.question_id WHERE r.student_id=? ORDER BY julianday(r.next_due)', (user['id'],)):
        schedules.setdefault(row['knowledge_id'], row)
    resource_rows = [dict(r) for r in db.execute('SELECT * FROM resources WHERE course_id=? ORDER BY id',(course_id,))]
    question_rows = [dict(r) for r in db.execute("SELECT * FROM questions WHERE course_id=? AND status='approved' AND type NOT IN ('short','step') ORDER BY difficulty,id",(course_id,))]
    teacher_focus = set()
    for task in db.execute("SELECT a.* FROM assignments a LEFT JOIN class_members m ON m.class_id=a.class_id AND m.student_id=? WHERE a.course_id=? AND a.status='published' AND (a.class_id IS NULL OR m.student_id IS NOT NULL)",(user['id'],course_id)):
        assigned = json.loads(task['student_ids'])
        if not assigned or user['id'] in assigned:
            teacher_focus.update(json.loads(task['question_ids']))
    by_id = {n['id']: n for n in nodes}
    parents = {n['id']: [] for n in nodes}
    for edge in db.execute('SELECT source,target FROM knowledge_edges WHERE course_id=?', (course_id,)):
        parents[edge['target']].append(edge['source'])
    goals = [dict(r) for r in db.execute("SELECT title,knowledge_ids FROM learning_goals WHERE student_id=? AND course_id=? AND status='active'", (user['id'], course_id))]

    def weak_ancestors(kid, visited=None):
        visited = set() if visited is None else visited
        result = []
        for pid in parents.get(kid, []):
            if pid in visited:
                continue
            visited.add(pid)
            result.extend(weak_ancestors(pid, visited))
            if states[pid]['value'] < .45:
                result.append(pid)
        return list(dict.fromkeys(result))

    result = []
    for node in nodes:
        kid = node['id']
        state = states[kid]
        wrong = wrongs.get(kid, 0)
        schedule = schedules.get(kid)
        due = bool(schedule and parse_time(schedule['next_due']) <= utc_now())
        if state['value'] >= .85 and not wrong and not due:
            continue
        weak = weak_ancestors(kid)
        video = next((r for r in resource_rows if r['knowledge_id']==kid and r['kind']=='video'), None)
        document = next((r for r in resource_rows if r['knowledge_id']==kid and r['kind']=='document'), None)
        question = next((q for q in question_rows if q['knowledge_id']==kid), None)
        if not question:
            continue
        query = f'course={course_id}&knowledge={kid}'
        steps = []
        if weak:
            pid = weak[0]
            steps.append({'kind': 'prerequisite', 'title': '先修：' + by_id[pid]['title'], 'href': f'/graph?course={course_id}&knowledge={pid}'})
        if video:
            timeline = json.loads(video['metadata']).get('timeline', [])
            timestamp = timeline[0].get('time', 0) if timeline else 0
            steps.append({'kind': 'video', 'title': '观看关键片段', 'href': f"/video?{query}&resource={video['id']}&t={timestamp}"})
        elif document:
            steps.append({'kind': 'document', 'title': '阅读知识卡', 'href': f"/resources?{query}&resource={document['id']}"})
        steps += [
            {'kind': 'practice', 'title': '针对性练习', 'href': f"/practice?{query}&question={question['id']}"},
            {'kind': 'check', 'title': '辅导与理解检查', 'href': f"/tutor?{query}&question={question['id']}"},
            {'kind': 'review', 'title': '间隔复测', 'href': f'/review?{query}'},
        ]
        related_goal = next((g for g in goals if kid in json.loads(g['knowledge_ids'])), None)
        reason = f'{wrong} 道错题待订正' if wrong else '复习已到期' if due else state['sufficiency']
        if weak:
            reason += f"；先巩固{by_id[weak[0]]['title']}"
        if related_goal:
            reason += f"；对应目标：{related_goal['title']}"
        kind = 'review' if wrong or due else 'video' if video and state['value'] < .45 else 'practice'
        href = f'/review?{query}' if wrong or due else steps[0]['href']
        priority = (1-state['value'])*50 + min(wrong, 3)*35 + due*20 + bool(related_goal)*10 - min(len(weak), 5)*2
        result.append({'id': f'{kind}-{kid}', 'course_id': course_id, 'knowledge_id': kid, 'title': node['title'],
                       'reason': reason, 'kind': kind, 'href': href, 'priority': round(priority, 2),
                       'mastery': round(state['value']*100), 'evidence': state, 'steps': steps,
                       'goal': bool(related_goal), 'teacher_task': question['id'] in teacher_focus, 'due': due, 'wrong': wrong,
                       'prerequisite_ids': weak, 'next_review_at': schedule['next_due'] if schedule else None,
                       'expected_change': '完成后补充独立作答证据；以实际结果更新状态', 'estimated_minutes': 8})
    return order_recommendations(result, parents, states)


def normalize(answer):
    return str(answer).strip().casefold().replace(' ', '').replace('（', '(').replace('）', ')')


def score_answer(question, answer):
    expected = json.loads(question['answer'])
    if question['type'] in ('short', 'step'):
        return None, 0, '待教师复核', 'pending_review'
    if question['type'] == 'multiple':
        actual = answer if isinstance(answer, list) else [answer]
        correct = {normalize(a) for a in actual} == {normalize(a) for a in expected}
    else:
        correct = normalize(answer) == normalize(expected)
    return correct, 100 if correct else 0, '', 'automatic'


def record_attempt(db, user, question, answer, hints_used=0, assignment_id=None, now=None, include_recommendations=True):
    now = now or utc_now()
    if user['role'] != 'student':
        raise HTTPException(403, '请使用学生账号提交作答')
    hints_used = max(0, min(int(hints_used), len(json.loads(question['hints']))))
    correct, score, error_type, review_status = score_answer(question, answer)
    if correct is False:
        error_type = diagnose_error(db, user['id'], question, answer)
    previous = db.execute('SELECT correct,created_at FROM attempts WHERE student_id=? AND question_id=? AND correct IS NOT NULL ORDER BY julianday(created_at) DESC,id DESC LIMIT 1', (user['id'], question['id'])).fetchone()
    cur = db.execute('INSERT INTO attempts(student_id,question_id,assignment_id,answer,correct,score,hints_used,error_type,review_status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                     (user['id'], question['id'], assignment_id, json.dumps(answer, ensure_ascii=False), None if correct is None else int(correct), score, hints_used, error_type, review_status, now.isoformat()))
    state = knowledge_state(db, user['id'], question['knowledge_id'], now)
    update, schedule = None, None
    if correct is not None:
        update, schedule = apply_evidence(db, user['id'], question, cur.lastrowid, correct, hints_used, previous, now)
        state = knowledge_state(db, user['id'], question['knowledge_id'], now)
        if not correct:
            db.execute('INSERT INTO mistakes(student_id,question_id,error_type,last_answer,next_review_at) VALUES(?,?,?,?,?) ON CONFLICT(student_id,question_id) DO UPDATE SET wrong_count=wrong_count+1,corrected=0,error_type=excluded.error_type,last_answer=excluded.last_answer,next_review_at=excluded.next_review_at',
                       (user['id'], question['id'], error_type, json.dumps(answer, ensure_ascii=False), schedule['next_due']))
        else:
            db.execute('UPDATE mistakes SET corrected=1,next_review_at=?,last_answer=? WHERE student_id=? AND question_id=?', (schedule['next_due'], json.dumps(answer, ensure_ascii=False), user['id'], question['id']))
    payload = {'attempt_id': cur.lastrowid, 'question_id': question['id'], 'correct': correct, 'hints_used': hints_used,
               'review_status': review_status, 'evidence': update, 'schedule': schedule}
    db.execute('INSERT INTO learning_events(student_id,course_id,knowledge_id,kind,payload,created_at) VALUES(?,?,?,?,?,?)',
               (user['id'], question['course_id'], question['knowledge_id'], 'attempt', json.dumps(payload, ensure_ascii=False), now.isoformat()))
    return {'id': cur.lastrowid, 'correct': correct, 'score': score, 'answer': json.loads(question['answer']),
            'explanation': question['explanation'], 'error_type': error_type, 'mastery': round(state['value']*100),
            'review_status': review_status, 'rubric': json.loads(question['rubric']), 'evidence': state,
            'review_schedule': schedule, 'recommendations': recommendations(db, user, question['course_id'])[:3] if include_recommendations else []}
