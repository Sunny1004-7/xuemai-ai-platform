"""第四轮隔离合成案例的机制对照；输出本次执行结果，不调用真实模型。"""
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import random
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_db
from backend.app.evidence import estimate_state, update_state
from backend.app.path_planner import plan_path, order_recommendations
from backend.app.learning_insights import dynamic_groups, learning_snapshot, WEIGHTS
from backend.app.teaching_agents import StrategyAgent

NOW=datetime(2026,11,11,tzinfo=timezone.utc)


def ktrace():
    state=estimate_state(now=NOW)
    cases=[]
    for difficulty in [1,2,3]:
        for peers in [0,4,8]:
            for hints in [0,1,2]:
                full=update_state(state,True,difficulty,hints,now=NOW,peer_count=peers)
                no_hint=update_state(state,True,difficulty,0,now=NOW,peer_count=peers)
                no_correlation=update_state(state,True,difficulty,hints,now=NOW)
                assert full['value']<=no_hint['value']+1e-9
                assert full['weight']<=no_correlation['weight']+1e-9
                cases.append({'difficulty':difficulty,'peers':peers,'hints':hints,'posterior':full['value'],
                    'without_hint_adjustment':no_hint['value'],'weight':full['weight'],'without_correlation_weight':no_correlation['weight']})
    repeated=update_state(state,True,3,0,{'correct':1,'created_at':(NOW-timedelta(hours=1)).isoformat()},NOW)
    assert repeated['weight']==0
    later=estimate_state({'alpha':12,'beta':4,'effective_count':12,'updated_at':NOW.isoformat()},NOW+timedelta(days=90))
    return {'cases':cases,'case_count':len(cases),'repeat_success_weight':repeated['weight'],
        'ninety_day_effective_count':later['effective_count'],'ninety_day_posterior':later['value'],
        'interpretation':'检验提示、相关性、重复成功与时间折减的计算行为'}


def pathg():
    rng=random.Random(4011)
    cases=[]
    for graph in range(12):
        count=8+graph%3*4
        parents={i:[j for j in range(1,i) if rng.random()<.16] for i in range(1,count+1)}
        states={i:estimate_state(now=NOW) for i in parents}
        goal=rng.randrange(2,count+1)
        candidates=[{'knowledge_id':i,'goal':i==goal,'estimated_minutes':8} for i in parents]
        for budget in [8,16,24,40]:
            plan=plan_path(candidates,parents,states,budget)
            baseline=sorted(candidates,key=lambda c:(not c['goal'],c['knowledge_id']))[:budget//8]
            def violations(ids):
                seen=set();bad=0
                for kid in ids:
                    bad+=sum(p not in seen for p in parents[kid]);seen.add(kid)
                return bad
            cases.append({'graph':graph,'nodes':count,'budget':budget,'goal':goal,
                'sequence':plan['knowledge_ids'],'minutes':plan['minutes'],
                'violations':violations(plan['knowledge_ids']),
                'static_goal_sort_violations':violations([c['knowledge_id'] for c in baseline])})
    assert all(c['violations']==0 and c['minutes']<=c['budget'] for c in cases)
    states={i:estimate_state(now=NOW) for i in [1,2,3,4]}
    parents={1:[],2:[1],3:[],4:[3]}
    items=[{'knowledge_id':i,'estimated_minutes':8,'goal':i==2} for i in states]
    before=plan_path(items,parents,states,16)['knowledge_ids']
    states[1] |= {'effective_count':6,'value':.8}
    after=plan_path(items,parents,states,16)['knowledge_ids']
    missing=order_recommendations([{'knowledge_id':2}],parents,{i:estimate_state(now=NOW) for i in states})
    assert missing==[] and before!=after
    return {'cases':cases,'case_count':len(cases),'prerequisite_violations':sum(c['violations'] for c in cases),
        'static_sort_violations':sum(c['static_goal_sort_violations'] for c in cases),'budget_violations':0,
        'evidence_replanning':{'before':before,'after_prerequisite_supported':after},'missing_prerequisite_blocked':not missing}


def classloop():
    rng=random.Random(4011)
    students=[];labels={}
    for i in range(24):
        focus=i%4
        vector=[.1]*4+[0,0];vector[focus]=.9
        delta=rng.uniform(-.015,.015)
        vector[0]+=delta;vector[1]-=delta
        students.append({'id':i+1,'features':vector,'recent_graded_count':20,'feature_confidence':[1]*6})
        labels[i+1]=focus
    questions=[{'id':i+1,'knowledge_id':i+1,'skill':skill,'difficulty':2} for i,skill in enumerate(['concept','procedure','reasoning','transfer'])]
    groups=dynamic_groups(students,questions)
    baseline=[{'student_ids':list(range(i*6+1,i*6+7))} for i in range(4)]
    def purity(groups):return sum(max(Counter(labels[i] for i in g['student_ids']).values()) for g in groups)/24
    def dispersion(groups):
        vectors={s['id']:s['features'] for s in students}
        result=0
        for group in groups:
            ids=group['student_ids']
            cost=lambda a:sum(sum(w*abs(x-y) for w,x,y in zip(WEIGHTS,vectors[a],vectors[b])) for b in ids)
            result+=min(cost(i) for i in ids)
        return result/24
    shuffled=students.copy();rng.shuffle(shuffled)
    shuffled_groups=dynamic_groups(shuffled,questions)
    membership=lambda gs:{frozenset(g['student_ids']) for g in gs}
    assert membership(groups)==membership(shuffled_groups)
    changed=[s|{'features':students[1]['features']} if s['id']==1 else s for s in students]
    after=dynamic_groups(changed,questions)
    destination=next(g for g in after if 1 in g['student_ids'])
    observation=dynamic_groups([{'id':100,'features':[.5]*6,'recent_graded_count':0,'feature_confidence':[0]*6}],questions)
    return {'students':24,'profiles':4,'classloop_purity':purity(groups),'equal_score_tiebreak_purity':purity(baseline),
        'classloop_mean_weighted_distance':dispersion(groups),'baseline_mean_weighted_distance':dispersion(baseline),
        'permutation_stable':True,'changed_student_focus':destination['focus'],
        'observation_focus':observation[0]['focus'],'group_sizes':[len(g['student_ids']) for g in groups]}


def diaguide(client,headers):
    def ask(conversation=None):
        response=client.post('/api/ai/chat',headers=headers,json={'course_id':1,'knowledge_id':2,'message':'我分不清出栈顺序，请引导我。','conversation_id':conversation})
        response.raise_for_status()
        return json.loads(response.text.split('event: done\ndata: ')[1].split('\n')[0])
    first=ask()
    feedback=client.post(f"/api/ai/checks/{first['teaching']['check']['id']}/answer",headers=headers,json={'answer':'不确定'}).json()
    second=ask(first['conversation_id'])
    assert not feedback['correct'] and second['teaching']['strategy']=='experiment'
    scenarios=[]
    for concern,errors,prereqs,failed,expected in [('证据不足',[],[],False,'hint'),('概念辨析',['概念混淆'],[],False,'contrast'),('先修缺口',[],[1],False,'contrast'),('准备独立复测',[],[],False,'check'),('概念辨析',['概念混淆'],[],True,'experiment')]:
        diagnosis={'concern':concern,'recent_errors':errors,'prerequisites':prereqs,'previous_feedback':{'correct':False} if failed else None}
        decision=StrategyAgent().run(diagnosis,[{'kind':k} for k in ['contrast','experiment','check']])
        scenarios.append({'concern':concern,'failed_feedback':failed,'expected':expected,'actual':decision['strategy'],'fixed_hint_baseline':'hint'})
    assert all(s['actual']==s['expected'] for s in scenarios)
    return {'scenarios':scenarios,'policy_matches':sum(s['actual']==s['expected'] for s in scenarios),
        'fixed_hint_matches':sum(s['fixed_hint_baseline']==s['expected'] for s in scenarios),
        'first_strategy':first['teaching']['strategy'],'after_failed_check':second['teaching']['strategy'],
        'roles':[r['role'] for r in second['teaching']['collaboration']['trace']],
        'verification':second['teaching']['collaboration']['verification'],'mock_chat_turns':2,
        'interpretation':'策略规则和执行衔接检查，匹配率不代表学习收益'}


def main(output=None):
    report={'executed_at':datetime.now(timezone.utc).isoformat(),'seed':4011,
        'data':'固定种子的隔离合成案例；机制指标与业务回归，不估计真实学生成绩提升','real_api_requests':0,
        'K-TRACE':ktrace(),'PATH-G':pathg(),'CLASS-LOOP':classloop()}
    with tempfile.TemporaryDirectory(prefix='xuemai-round4-') as folder:
        os.environ.update(DATABASE_PATH=str(Path(folder)/'methods.db'),AI_MODE='mock',XUEMAI_DEMO_COHORT='1')
        with TestClient(app) as client:
            token=client.post('/api/auth/login',json={'username':'student1','password':'Xuemai123!'}).json()['token']
            report['DIA-GUIDE']=diaguide(client,{'Authorization':'Bearer '+token})
            with get_db() as db:
                members=[r[0] for r in db.execute('SELECT student_id FROM class_members WHERE class_id=1')]
                queries=[];db.set_trace_callback(queries.append)
                start=time.perf_counter();snapshot=learning_snapshot(db,1,members);elapsed=time.perf_counter()-start
                db.set_trace_callback(None)
                report['cohort_snapshot']={'students':len(members),'graded_attempts':snapshot['summary']['attempt_count'],
                    'selects':sum(q.lstrip().upper().startswith('SELECT') for q in queries),'elapsed_ms':round(elapsed*1000,2)}
    output=ROOT/(output or 'docs/rounds/第四轮核心方法对照.json')
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:{a:b for a,b in v.items() if a not in ['cases','scenarios']} if isinstance(v,dict) else v for k,v in report.items()},ensure_ascii=False,indent=2))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output');args=parser.parse_args();main(args.output)
