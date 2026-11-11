"""DIA-GUIDE：诊断、策略、校验通过类型明确的共享状态协作。

诊断和校验代理使用可检查的规则与数据库工具，策略代理消费诊断后指导一次模型生成。
持久记录的是证据、决策和校验结果，不包含模型内部推理。
"""
import json
from .evidence import knowledge_state


class DiagnosisAgent:
    name = '学习诊断代理'

    def run(self, db, user_id, course_id, kid, conversation_id):
        state = knowledge_state(db,user_id,kid)
        attempts = [dict(r) for r in db.execute('SELECT a.correct,a.hints_used,a.error_type,q.skill FROM attempts a JOIN questions q ON q.id=a.question_id WHERE a.student_id=? AND q.knowledge_id=? AND a.correct IS NOT NULL ORDER BY julianday(a.created_at) DESC,a.id DESC LIMIT 8',(user_id,kid))]
        prerequisites = []
        for p in db.execute('SELECT k.id,k.title FROM knowledge_edges e JOIN knowledge_points k ON k.id=e.source WHERE e.target=?',(kid,)):
            ps=knowledge_state(db,user_id,p['id'])
            if not ps['observed'] or ps['value']<.45:
                prerequisites.append(dict(p)|{'observed':ps['observed'],'value':round(ps['value'],3)})
        previous=db.execute("SELECT state FROM teaching_runs WHERE user_id=? AND conversation_id=? AND knowledge_id=? AND status='feedback' ORDER BY id DESC LIMIT 1",(user_id,conversation_id,kid)).fetchone()
        feedback=json.loads(previous[0]).get('feedback') if previous else None
        concern = '先修缺口' if prerequisites else '证据不足' if not attempts else '提示依赖' if sum(a['hints_used']>0 for a in attempts)/len(attempts)>.5 else next((a['error_type'] for a in attempts if a['correct']==0),'准备独立复测')
        return {'role':self.name,'knowledge_id':kid,'concern':concern,'evidence_count':round(state['effective_count'],2),
                'uncertainty':[round(state['lower'],3),round(state['upper'],3)],'prerequisites':prerequisites,
                'recent_errors':[a['error_type'] for a in attempts if a['correct']==0], 'previous_feedback':feedback,
                'tools':['knowledge_state','recent_attempts','prerequisite_lookup','check_feedback']}


class StrategyAgent:
    name = '教学策略代理'

    def run(self, diagnosis, candidates):
        concern=diagnosis['concern']
        failed=diagnosis['previous_feedback'] and not diagnosis['previous_feedback']['correct']
        preferred='experiment' if failed or diagnosis.get('intent')=='procedure' else 'contrast' if diagnosis['prerequisites'] or diagnosis['recent_errors'] or diagnosis.get('intent')=='contrast' else 'check' if concern=='准备独立复测' else 'hint'
        available={a['kind'] for a in candidates}
        if preferred not in available and preferred!='hint':
            preferred='contrast' if 'contrast' in available else 'hint'
        selected=[a for a in candidates if a['kind'] in {preferred,'check'}]
        if not selected:
            selected=candidates
        return {'role':self.name,'strategy':preferred,'actions':selected,
                'objective':'复测失败后更换表征方式' if failed else concern,
                'instruction':f"教学关注：{concern}。采用{preferred}策略，一次只处理一个困难。"}


class VerificationAgent:
    name = '教学校验代理'

    def run(self, plan, content, citations, db=None):
        from urllib.parse import urlsplit,parse_qs
        valid=[]
        rejected=[]
        run=db.execute('SELECT * FROM teaching_runs WHERE id=?',((plan.get('collaboration') or {}).get('run_id'),)).fetchone() if db else None
        def mapped(action):
            if not db or not run:return False
            if action.get('kind')=='check':
                return bool(db.execute('SELECT 1 FROM tutoring_checks t JOIN questions q ON q.id=t.question_id WHERE t.id=? AND t.user_id=? AND t.conversation_id=? AND q.course_id=? AND q.knowledge_id=?',(action.get('check_id'),run['user_id'],run['conversation_id'],run['course_id'],run['knowledge_id'])).fetchone()) and action.get('check_id')==(plan.get('check') or {}).get('id')
            url=urlsplit(action.get('href','')); query=parse_qs(url.query)
            if url.scheme or url.netloc or url.path not in ('/graph','/video','/experiments'):return False
            try:
                if int(query.get('course',[0])[0])!=run['course_id'] or int(query.get('knowledge',[0])[0])!=run['knowledge_id']:return False
                if not db.execute('SELECT 1 FROM knowledge_points WHERE id=? AND course_id=?',(run['knowledge_id'],run['course_id'])).fetchone():return False
                if action['kind']=='video':
                    resource=db.execute("SELECT * FROM resources WHERE id=? AND course_id=? AND kind='video'",(int(query.get('resource',[0])[0]),run['course_id'])).fetchone()
                    if not resource or url.path!='/video':return False
                    metadata=json.loads(resource['metadata'] or '{}')
                    linked=resource['knowledge_id']==run['knowledge_id'] or any(t.get('knowledge_id')==run['knowledge_id'] for t in metadata.get('timeline',[]))
                    timestamp=float(query.get('t',[0])[0])
                    return linked and 0<=timestamp<=float(metadata.get('duration',0))
                if action['kind']=='experiment':
                    return url.path=='/experiments' and bool(db.execute('SELECT 1 FROM knowledge_activities WHERE knowledge_id=? AND mode=?',(run['knowledge_id'],query.get('mode',[''])[0])).fetchone())
                return action['kind']=='contrast' and url.path=='/graph'
            except (TypeError,ValueError):return False
        for action in plan['actions']:
            if mapped(action):
                valid.append(action)
            else:
                rejected.append(action.get('kind','unknown'))
        import re
        refs=[int(r) for r in re.findall(r'\[(\d+)\]',content)]
        bad_refs=[r for r in refs if r<1 or r>len(citations)]
        if db and run:
            for index,citation in enumerate(citations,1):
                if citation.get('source_kind')=='attachment':
                    valid_source=db.execute('SELECT 1 FROM ai_attachments WHERE id=? AND user_id=? AND course_id=? AND conversation_id=? AND deleted_at IS NULL',(citation.get('attachment_id'),run['user_id'],run['course_id'],run['conversation_id'])).fetchone()
                else:
                    valid_source=db.execute('SELECT 1 FROM resources WHERE id=? AND course_id=?',(citation.get('resource_id'),run['course_id'])).fetchone()
                if not valid_source:bad_refs.append(index)
        from .retrieval import citation_support
        return {'role':self.name,'passed':bool(valid) and not bad_refs and not rejected,'actions':valid,
                'rejected_actions':rejected,'invalid_references':bad_refs,
                'citation_support':citation_support(content,citations),
                'checks':['课程对象映射','可执行动作类型','理解检查关联','资料引用位置与词项支持']}


def begin_collaboration(db,user,request,conversation_id,plan):
    diagnosis=DiagnosisAgent().run(db,user['id'],request.course_id,plan['knowledge_id'],conversation_id)
    diagnosis['intent']=plan.get('intent','concept')
    decision=StrategyAgent().run(diagnosis,plan['actions'])
    plan['strategy']=decision['strategy']
    plan['actions']=decision['actions']
    shared={'method':'DIA-GUIDE','version':3,'diagnosis':diagnosis,'decision':decision,
            'trace':[{'role':diagnosis['role'],'result':diagnosis['concern']},
                     {'role':decision['role'],'result':decision['objective']}],
            'model_calls_limit':1,'transition':'diagnosed → planned'}
    run_id=db.execute('INSERT INTO teaching_runs(conversation_id,user_id,course_id,knowledge_id,check_id,state) VALUES(?,?,?,?,?,?)',
        (conversation_id,user['id'],request.course_id,plan['knowledge_id'],(plan.get('check') or {}).get('id'),json.dumps(shared,ensure_ascii=False))).lastrowid
    plan['collaboration']=shared|{'run_id':run_id}
    return plan


def finalize_collaboration(db,plan,content,citations):
    shared=plan.get('collaboration')
    if not shared:
        return content,plan
    verification=VerificationAgent().run(plan,content,citations,db)
    shared['verification']={k:v for k,v in verification.items() if k!='actions'}
    shared['trace'].append({'role':verification['role'],'result':'动作与引用已校验' if verification['passed'] else '已移除未通过校验的引用或动作'})
    has_check=any(a['kind']=='check' for a in verification['actions'])
    status='awaiting_check' if verification['passed'] and has_check else 'verified' if verification['passed'] else 'partial' if verification['actions'] else 'needs_revision'
    shared['transition']='planned → '+status
    shared['status']=status
    plan['actions']=verification['actions']
    if not has_check:plan['check']=None
    if verification['invalid_references']:
        for r in verification['invalid_references']:
            content=content.replace(f'[{r}]','')
    db.execute("UPDATE teaching_runs SET state=?,status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(json.dumps(shared,ensure_ascii=False),status,shared['run_id']))
    return content,plan


def record_feedback(db,check_id,result):
    run=db.execute('SELECT * FROM teaching_runs WHERE check_id=? ORDER BY id DESC LIMIT 1',(check_id,)).fetchone()
    if run:
        shared=json.loads(run['state'])
        shared['feedback']={'correct':result['correct'],'attempt_id':result['id'],'next_action':result['next_action']}
        shared['trace'].append({'role':'理解反馈','result':'安排间隔复测' if result['correct'] else '下一轮更换教学策略'})
        shared['transition']=run['status']+' → feedback'
        shared['status']='feedback'
        db.execute("UPDATE teaching_runs SET state=?,status='feedback',updated_at=CURRENT_TIMESTAMP WHERE id=?",(json.dumps(shared,ensure_ascii=False),run['id']))
        return shared
