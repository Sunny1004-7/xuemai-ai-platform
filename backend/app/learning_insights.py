"""批量学习投影与CLASS-LOOP动态错因聚类，无每学生每节点查询。"""
from collections import Counter, defaultdict
from datetime import timedelta
import json
from .evidence import estimate_state, parse_time, utc_now

FEATURES = ['概念辨析','操作步骤','推理论证','迁移应用','提示依赖','学习参与']
SKILLS = ['concept','procedure','reasoning','transfer']
WEIGHTS = [1.2,1.2,1.,1.1,.8,.7]


def dynamic_groups(students, questions, max_groups=4):
    """确定性加权L1 k-medoids；组别根据当次证据重新计算。"""
    if not students:
        return []
    observation = [s for s in students if s.get('recent_graded_count', 2) < 2]
    students = [s for s in students if s not in observation]
    observation_groups = []
    if observation:
        starters = sorted(questions, key=lambda q:(q['difficulty'],q['id']))[:3]
        observation_groups.append({'id':'group-observation', 'name':'学习起点观察组',
            'student_ids':[s['id'] for s in observation], 'features':dict.fromkeys(FEATURES,0),
            'focus':'补充学习证据', 'strategy':'先完成少量独立练习，再根据作答安排针对性任务',
            'question_ids':[q['id'] for q in starters], 'knowledge_id':starters[0]['knowledge_id'] if starters else None,
            'method':'CLASS-LOOP', 'medoid':None, 'dispersion':0, 'evidence_level':'观察中'})
    if not students:
        return observation_groups
    vectors = {s['id']: s['features'] for s in students}
    confidence = {s['id']:s.get('feature_confidence',[1]*len(FEATURES)) for s in students}
    def distance(a,b):
        # 共有证据决定差异；支持程度差异给予小幅惩罚，未知维度不当成相同错因。
        return sum(w*(min(ca,cb)*abs(x-y)+.25*abs(ca-cb))
                   for w,x,y,ca,cb in zip(WEIGHTS,vectors[a],vectors[b],confidence[a],confidence[b]))
    ids = sorted(vectors)
    medoids = [ids[0]]
    for _ in range(min(max(1,max_groups-len(observation_groups)),len(ids))-1):
        medoids.append(max((i for i in ids if i not in medoids),key=lambda i:(min(distance(i,m) for m in medoids),-i)))
    clusters = {}
    for _ in range(12):
        clusters = {m: [] for m in medoids}
        for sid in ids:
            closest = min(medoids,key=lambda m:(distance(sid,m),m))
            clusters[closest].append(sid)
        updated = [min(members,key=lambda candidate:(sum(distance(candidate,j) for j in members),candidate)) if members else m for m,members in clusters.items()]
        if updated == medoids:
            break
        medoids = updated
    # 以最终中心重新分配，避免最后一次更新后仍返回旧成员。
    clusters = {m:[] for m in medoids}
    for sid in ids:
        clusters[min(medoids,key=lambda m:(distance(sid,m),m))].append(sid)
    output = []
    for m,members in clusters.items():
        if not members:
            continue
        center = [sum(vectors[i][j]*confidence[i][j] for i in members)/max(.001,sum(confidence[i][j] for i in members)) for j in range(len(FEATURES))]
        focus = max(range(len(center)),key=lambda j:center[j])
        weak=Counter(kid for s in students if s['id'] in members for kid in s.get('weak_knowledge_ids',[]))
        candidates = sorted(questions,key=lambda q:(-weak[q['knowledge_id']],-(2 if focus<4 and q['skill']==SKILLS[focus] else 0),q['difficulty'] if focus>=4 else abs(q['difficulty']-2),q['id']))
        qids = [q['id'] for q in candidates[:3]]
        strategies = ['用反例区分概念边界','逐步追踪状态并检查操作顺序','补齐推理依据与边界条件','更换输入检验知识迁移','减少提示后进行独立复测','安排短任务恢复学习节奏']
        output.append({'id':f'group-{m}', 'name':FEATURES[focus]+'关注组', 'student_ids':members,
                       'features':dict(zip(FEATURES,[round(v,3) for v in center])), 'focus':FEATURES[focus],
                       'strategy':strategies[focus], 'question_ids':qids,'weak_knowledge_ids':[k for k,_ in weak.most_common(5)],
                       'knowledge_id':candidates[0]['knowledge_id'] if candidates else None,
                       'method':'CLASS-LOOP', 'medoid':m, 'dispersion':round(sum(distance(i,m) for i in members)/len(members),3)})
    return output + observation_groups


def learning_snapshot(db, course_id, student_ids, now=None):
    now = now or utc_now()
    selected = set(student_ids)
    nodes = [dict(r) for r in db.execute('SELECT k.*,c.title chapter_title FROM knowledge_points k LEFT JOIN chapters c ON c.id=k.chapter_id WHERE k.course_id=? ORDER BY c.position,k.id',(course_id,))]
    students = [dict(r) for r in db.execute("SELECT id,name FROM users WHERE active=1 ORDER BY id") if r['id'] in selected]
    rows = {(r['student_id'],r['knowledge_id']):r for r in db.execute('SELECT m.* FROM mastery m JOIN knowledge_points k ON k.id=m.knowledge_id WHERE k.course_id=?',(course_id,)) if r['student_id'] in selected}
    states = {(s['id'],n['id']):estimate_state(rows.get((s['id'],n['id'])),now) for s in students for n in nodes}
    attempts = [dict(r) for r in db.execute('SELECT a.*,q.knowledge_id,q.skill,q.difficulty FROM attempts a JOIN questions q ON q.id=a.question_id WHERE q.course_id=? ORDER BY julianday(a.created_at),a.id',(course_id,)) if r['student_id'] in selected]
    by_student = defaultdict(list)
    for a in attempts:
        by_student[a['student_id']].append(a)
    heatmap = []
    for s in students:
        observed = [states[(s['id'],n['id'])] for n in nodes if states[(s['id'],n['id'])]['observed']]
        graded = [a for a in by_student[s['id']] if a['correct'] is not None]
        recent = [a for a in graded if (now-parse_time(a['created_at'])).days<14]
        features = []
        feature_confidence = []
        for skill in SKILLS:
            subset = [a for a in recent if a['skill']==skill]
            features.append(sum(1-a['score']/100 for a in subset)/len(subset) if subset else .5)
            feature_confidence.append(min(1,len(subset)/4))
        features.append(sum(a['hints_used']>0 for a in recent)/len(recent) if recent else 0)
        gap = max(0,(now-parse_time(graded[-1]['created_at'])).total_seconds()/86400) if graded else 14
        features.append(min(1,gap/14))
        feature_confidence += [min(1,len(recent)/6),1 if graded else 0]
        s.update(mastery=round(sum(v['value'] for v in observed)/len(observed)*100) if observed else 0,
                 attempts=len(graded),accuracy=round(sum(a['correct'] for a in graded)/len(graded)*100) if graded else 0,
                 evidence_sufficiency=sum(v['effective_count']>=2 for v in observed),coverage=len(observed),features=features,
                 recent_graded_count=len(recent),feature_confidence=feature_confidence)
        s['weak_knowledge_ids']=[n['id'] for n in nodes if states[(s['id'],n['id'])]['observed'] and states[(s['id'],n['id'])]['value']<.6]
        heatmap.append({'student_id':s['id'],'name':s['name'],'cells':[{'knowledge_id':n['id'],'value':round(states[(s['id'],n['id'])]['value']*100) if states[(s['id'],n['id'])]['observed'] else None,'count':round(states[(s['id'],n['id'])]['effective_count'],1)} for n in nodes]})
    knowledge=[]
    for n in nodes:
        observed=[(s,states[(s['id'],n['id'])]) for s in students if states[(s['id'],n['id'])]['observed']]
        distribution=Counter('mastered' if st['value']>=.75 else 'learning' if st['value']>=.4 else 'weak' for _,st in observed)
        distribution['unknown']=len(students)-len(observed)
        knowledge.append(n | {'average_mastery':round(sum(st['value'] for _,st in observed)/len(observed)*100) if observed else 0,
                             'observed_count':len(observed),'distribution':dict(distribution),
                             'weak_students':[dict(s)|{'mastery':round(st['value']*100),'evidence':st} for s,st in observed if st['value']<.5]})
    daily=[]
    for back in range(13,-1,-1):
        day=(now-timedelta(days=back)).date().isoformat()
        items=[a for a in attempts if a['correct'] is not None and parse_time(a['created_at']).date().isoformat()==day]
        daily.append({'day':day,'count':len(items),'accuracy':round(sum(a['correct'] for a in items)/len(items)*100) if items else None})
    all_observed=[s for s in states.values() if s['observed']]
    graded=[a for a in attempts if a['correct'] is not None]
    errors=Counter(a['error_type'] for a in graded if not a['correct'])
    events=[dict(r) for r in db.execute('SELECT student_id,kind,payload,created_at FROM learning_events WHERE course_id=?',(course_id,)) if r['student_id'] in selected]
    activities=Counter(e['kind'] for e in events)
    skill_profiles=[]
    for skill in SKILLS:
        items=[a for a in graded if a['skill']==skill]
        skill_profiles.append({'skill':skill,'name':FEATURES[SKILLS.index(skill)],'count':len(items),'performance':round(sum(a['score'] for a in items)/len(items)) if items else None})
    return {'summary':{'student_count':len(students),'average_mastery':round(sum(s['value'] for s in all_observed)/len(all_observed)*100) if all_observed else 0,
                       'attempt_count':len(graded),'accuracy':round(sum(a['correct'] for a in graded)/len(graded)*100) if graded else 0,
                       'coverage':len(all_observed),'possible_evidence':len(students)*len(nodes)},
            'students':students,'knowledge':knowledge,'heatmap':heatmap,'trend':daily,'skills':skill_profiles,
            'activities':[{'kind':k,'count':v} for k,v in activities.items()],
            'error_distribution':[{'name':k,'value':v} for k,v in errors.most_common()], 'metric':'observed-knowledge-mean',
            'generated_at':now.isoformat()}
