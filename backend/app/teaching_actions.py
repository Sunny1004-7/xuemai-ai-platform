"""模型只选择受支持的动作；对象、权限和评分始终由业务层约束。"""
import json
from .evidence import knowledge_state

MARKER = '<!--XM_ACTIONS:'


def learning_intent(message):
    for intent, terms in [('procedure',['步骤','操作','为什么错']),('contrast',['反例','区别','辨析']),('hint',['提示','不要答案']),('example',['例子','例题']),('transfer',['变式','迁移']),('summary',['复习','总结'])]:
        if any(term in message for term in terms):return intent
    return 'concept'


def prepare_actions(db, user, request, conversation_id):
    from .activity_catalog import infer_knowledge, video_location
    kid = infer_knowledge(db, request)
    if not kid:
        return {'strategy':'hint','actions':[],'check':None}
    point = db.execute('SELECT title,description FROM knowledge_points WHERE id=?', (kid,)).fetchone()
    query = f'course={request.course_id}&knowledge={kid}'
    candidates = [{'kind':'contrast','title':'查看概念与先修关系','href':f'/graph?{query}'}]
    video = db.execute("SELECT * FROM resources WHERE course_id=? AND kind='video' AND (knowledge_id=? OR EXISTS(SELECT 1 FROM json_each(metadata,'$.timeline') t WHERE json_extract(t.value,'$.knowledge_id')=?)) ORDER BY id LIMIT 1", (request.course_id,kid,kid)).fetchone()
    if video:
        timestamp=video_location(video,kid,request.video_timestamp if request.resource_id==video['id'] else None)
        candidates.append({'kind':'video','title':'定位关键视频片段','href':f"/video?{query}&resource={video['id']}&t={timestamp:g}"})
    modes=[row[0] for row in db.execute('SELECT mode FROM knowledge_activities WHERE knowledge_id=? ORDER BY mode',(kid,))]
    mode='queue' if 'queue' in modes and '队列' in getattr(request,'message','') else modes[0] if modes else None
    if mode:
        candidates.append({'kind':'experiment','title':'逐步运行交互实验','href':f'/experiments?{query}&mode={mode}'})
    question = db.execute("SELECT * FROM questions WHERE knowledge_id=? AND status='approved' AND type NOT IN ('short','step') ORDER BY CASE WHEN id=? THEN 1 ELSE 0 END,difficulty,id LIMIT 1", (kid, request.question_id or 0)).fetchone()
    check = None
    if question and user['role'] == 'student':
        check_id = db.execute('INSERT INTO tutoring_checks(user_id,conversation_id,question_id) VALUES(?,?,?)', (user['id'], conversation_id, question['id'])).lastrowid
        check = {'id': check_id, 'title': question['title'], 'type': question['type'], 'options': json.loads(question['options']), 'knowledge_id': kid}
        candidates.append({'kind':'check','title':'完成理解检查','check_id':check_id})
    recent = db.execute('SELECT correct,error_type FROM attempts a JOIN questions q ON q.id=a.question_id WHERE a.student_id=? AND q.knowledge_id=? ORDER BY a.id DESC LIMIT 1', (user['id'], kid)).fetchone()
    strategy = 'contrast' if recent and recent['correct'] == 0 else 'check' if knowledge_state(db,user['id'],kid)['value'] > .5 else 'hint'
    return {'strategy':strategy,'intent':learning_intent(getattr(request,'message','')),'actions':candidates,'check':check,'knowledge_id':kid,'knowledge_title':point['title'],'concept':point['description']}


def validate_selection(content, plan):
    """将模型选择映射为已授权能力，绝不执行模型提供的URL或对象ID。"""
    visible, sep, raw = content.partition(MARKER)
    requested = []
    if sep:
        try:
            item = json.loads(raw.split('-->',1)[0])
            requested = item.get('kinds', []) if isinstance(item,dict) else []
            if item.get('strategy') in ('hint','contrast','experiment','video','check'):
                plan['strategy'] = item['strategy']
        except (ValueError, TypeError, AttributeError):
            pass
    if not isinstance(requested,list):
        requested = []
    selected = [a for a in plan['actions'] if a['kind'] in requested]
    # 检查始终保留，模型无有效结构输出时采用完整的受限动作集。
    plan['actions'] = selected + [a for a in plan['actions'] if a['kind']=='check' and a not in selected] if selected else plan['actions']
    return visible.strip(), plan
