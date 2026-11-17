"""第十轮冻结实验入口。离线默认不联网，付费实验必须显式 --real。"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.evidence import estimate_state, update_state
from backend.app.path_planner import plan_path
from backend.app.learning_insights import dynamic_groups
from scripts.validate_round7_methods import constrained_greedy, pair_agreement, membership

OUT=ROOT/'docs/experiments/round10'
SEED=101711
NOW=datetime(2026,11,17,tzinfo=timezone.utc)


def save(name, value):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')


def mean(values):
    return round(statistics.mean(values),6) if values else None


def exact_path(candidates, parents, states, budget, components):
    """子集DP，每个集合的成本和长度相同，只保留最高效用前缀。"""
    ready={k for k,s in states.items() if s['value']>=.6 and s['effective_count']>=2}
    best={0:(0.,[])}
    keys=[c['knowledge_id'] for c in candidates]
    costs={c['knowledge_id']:c['estimated_minutes'] for c in candidates}
    for mask in range(1<<len(keys)):
        if mask not in best:
            continue
        score,path=best[mask]
        used=sum(costs[k] for k in path)
        for i,k in enumerate(keys):
            if mask&(1<<i) or used+costs[k]>budget or any(p not in ready and p not in path for p in parents[k]):
                continue
            value=score+sum(components[k].values())*.92**len(path)-.06*costs[k]
            target=mask|(1<<i)
            if target not in best or value>best[target][0]:
                best[target]=(value,path+[k])
    return max(best.values(),key=lambda x:x[0])


def path_experiment():
    rng=random.Random(SEED)
    cases=[]
    for graph in range(200):
        count=[6,9,16,24,32][graph%5]
        parents={k:[p for p in range(1,k) if rng.random()<[.06,.16,.28][graph%3]] for k in range(1,count+1)}
        states={k:estimate_state(now=NOW) for k in parents}
        for k in states:
            if rng.random()<.2:
                states[k]|={'value':.8,'effective_count':4}
        goals=set(rng.sample(list(parents),1+graph%3))
        candidates=[{'knowledge_id':k,'estimated_minutes':rng.choice([3,5,8,12]),'goal':k in goals,
                     'teacher_task':rng.random()<.2,'due':rng.random()<.25,'wrong':rng.randrange(4)}
                    for k in parents if rng.random()>.08]
        for budget in [10,20,30,60]:
            begin=time.perf_counter()
            plan=plan_path(candidates,parents,states,budget)
            elapsed=(time.perf_counter()-begin)*1000
            components=plan['components']
            costs={c['knowledge_id']:c['estimated_minutes'] for c in candidates}
            static=[];spent=0
            for c in sorted(candidates,key=lambda c:(not c['goal'],c['knowledge_id'])):
                if spent+c['estimated_minutes']<=budget:
                    static.append(c['knowledge_id']);spent+=c['estimated_minutes']
            methods={'PATH-G':plan['knowledge_ids'],
                     'feasible_greedy':constrained_greedy(candidates,parents,states,budget,components),
                     'static_goal':static}
            optimum=exact_path(candidates,parents,states,budget,components)[0] if count<=9 else None
            rows={}
            for method,seq in methods.items():
                seen={k for k,s in states.items() if s['value']>=.6 and s['effective_count']>=2}
                violations=0
                for k in seq:
                    violations+=sum(p not in seen for p in parents[k]);seen.add(k)
                used=sum(costs[k] for k in seq)
                utility=sum(sum(components[k].values())*.92**i-.06*costs[k] for i,k in enumerate(seq))
                rows[method]={'sequence':seq,'utility':utility,'prerequisite_violations':violations,
                              'budget_violation':used>budget,'budget_utilization':used/budget,
                              'goal_coverage':len(goals&set(seq))/len(goals)}
            # 更新证据和任务后重新调用正式规划器。
            changed=deepcopy(states)
            if plan['knowledge_ids']:
                changed[plan['knowledge_ids'][0]]|={'value':.9,'effective_count':6}
            replanned=plan_path(candidates,parents,changed,budget)
            cases.append({'graph':graph,'split':'dev' if graph<20 else 'eval','budget':budget,
                          'parents':parents,'candidates':candidates,'states':states,'outcomes':rows,
                          'exact_utility':optimum,'runtime_ms':elapsed,'expanded':plan['expanded'],
                          'replanned':replanned})
    evaluated=[c for c in cases if c['split']=='eval']
    summary={m:{k:mean([c['outcomes'][m][k] for c in evaluated]) for k in
               ['utility','goal_coverage','budget_utilization']} for m in methods}
    for m in methods:
        summary[m]|={k:sum(c['outcomes'][m][k] for c in evaluated) for k in ['prerequisite_violations','budget_violation']}
    diffs=[c['outcomes']['PATH-G']['utility']-c['outcomes']['feasible_greedy']['utility'] for c in evaluated]
    exact=[c for c in evaluated if c['exact_utility'] is not None and c['exact_utility']>0]
    return {'independent_graphs':180,'evaluation_cases':len(evaluated),'cases':cases,'summary':summary,
            'wins_ties_losses':[sum(x>1e-5 for x in diffs),sum(abs(x)<=1e-5 for x in diffs),sum(x<-1e-5 for x in diffs)],
            'exact_reference_cases':len(exact),'mean_optimality_ratio':mean([c['outcomes']['PATH-G']['utility']/c['exact_utility'] for c in exact]),
            'runtime_ms_mean':mean([c['runtime_ms'] for c in evaluated])}


def ktrace_experiment():
    rng=random.Random(SEED+1);cases=[]
    for index in range(1320):
        family=index%6
        length=[4,8,16,32,48][index%5]
        latent=rng.uniform(.2,.9)
        now=NOW
        events=[]
        states={m:estimate_state(now=now) for m in ['K-TRACE','no_decay','no_hints','no_correlation','fixed_step']}
        previous=None;repeat_violations=0
        errors={m:[] for m in states}
        for step in range(length):
            gap=rng.choice([0,.02,.5,2,15,45])
            now+=timedelta(days=gap)
            # Independent generator: logistic difficulty, slip/guess, random-walk progress.
            # Family 4 uses abrupt state changes, family 5 no forgetting.
            if family!=5:
                latent=max(.05,min(.95,latent*math.exp(-gap/120)+rng.uniform(-.025,.045)))
            if family==4 and step==length//2:
                latent=1-latent
            difficulty=rng.randint(1,3);hints=rng.randrange(3) if family in [1,3] else 0
            probability=.12+.78/(1+math.exp(-5*(latent-.5)+.6*(difficulty-2)-.7*hints))
            correct=rng.random()<probability
            partial=(rng.uniform(20,70) if not correct and family==2 else 100 if correct else 0)
            repeated=family==3 and step%3!=0
            peers=step%8 if family in [2,3] else 0
            event={'correct':correct,'difficulty':difficulty,'hints':hints,'score':partial,'peer_count':peers,
                   'at':now.isoformat(),'latent':latent,'repeat':repeated}
            events.append(event)
            for method,state in states.items():
                if method=='fixed_step':
                    state['value']=max(0,min(1,state['value']+(.08 if correct else -.08)))
                else:
                    state=estimate_state(state, now if method!='no_decay' else datetime.fromisoformat(state.get('updated_at',now.isoformat())))
                    before=state['value']
                    change=update_state(state,correct,difficulty,0 if method=='no_hints' else hints,
                                        previous if repeated else None,now,0 if method=='no_correlation' else peers,partial)
                    state|=change
                    if method=='K-TRACE' and repeated and previous and correct and previous['correct'] and gap<1:
                        repeat_violations+=abs(state['value']-before)>1e-10
                    if change['weight']>0:
                        state['updated_at']=now.isoformat()
                states[method]=state
                errors[method].append((state['value']-latent)**2)
            previous={'correct':correct,'created_at':now.isoformat()}
        cases.append({'id':index,'split':'dev' if index<120 else 'eval','family':family,'events':events,
                      'rmse':{m:math.sqrt(statistics.mean(e)) for m,e in errors.items()},
                      'final':states,'repeat_violations':repeat_violations})
    rows=[c for c in cases if c['split']=='eval']
    return {'evaluation_trajectories':len(rows),'events':sum(len(c['events']) for c in rows),
            'summary':{m:mean([c['rmse'][m] for c in rows]) for m in states},
            'by_family':{str(f):{m:mean([c['rmse'][m] for c in rows if c['family']==f]) for m in states} for f in range(6)},
            'repeat_violations':sum(c['repeat_violations'] for c in rows),'cases':cases}


def class_experiment():
    rng=random.Random(SEED+2);cases=[]
    questions=[{'id':k*4+s+1,'knowledge_id':k+1,'skill':skill,'difficulty':2}
               for k in range(4) for s,skill in enumerate(['concept','procedure','reasoning','transfer'])]
    for index in range(54):
        count=[16,28,48,80][index%4];students=[]
        for i in range(count):
            label=i%4;features=[max(0,min(1,rng.gauss(.82 if j==label else .12,.05+index%3*.03))) for j in range(6)]
            confidence=[1.]*6
            if index%6 in [2,3]:
                missing=(i+1)%4;confidence[missing]=0;features[missing]=rng.random()
            n=0 if index%6==3 and i%7==0 else 12
            if index%6==4 and i%5==0:
                features[(label+1)%4]=.72
            students.append({'id':i+1,'features':features,'feature_confidence':confidence,'recent_graded_count':n,
                             'weak_knowledge_ids':[label+1],'reference':label})
        begin=time.perf_counter();groups=dynamic_groups(students,questions);elapsed=(time.perf_counter()-begin)*1000
        ablated=dynamic_groups([s|{'feature_confidence':[1]*6} for s in students],questions)
        shuffled=students.copy();rng.shuffle(shuffled)
        sparse={s['id'] for s in students if s['recent_graded_count']<2}
        detected={sid for g in groups if g.get('evidence_level')=='观察中' for sid in g['student_ids']}
        # Pair agreement with known single prototypes only. Mixed-difficulty families use stability.
        reference=[{'student_ids':[s['id'] for s in students if s['reference']==label]} for label in range(4)]
        score_groups=[]
        ordered=sorted(students,key=lambda s:sum(s['features']))
        for q in range(4):
            score_groups.append({'student_ids':[s['id'] for s in ordered[q*count//4:(q+1)*count//4]]})
        matching=[]
        for g in groups:
            if g.get('evidence_level')=='观察中':continue
            weak=Counter(k for s in students if s['id'] in g['student_ids'] for k in s['weak_knowledge_ids'])
            expected={k for k,n in weak.items() if n==max(weak.values())}
            matching.append(next(q['knowledge_id'] for q in questions if q['id']==g['question_ids'][0]) in expected)
        cases.append({'id':index,'split':'dev' if index<6 else 'eval','family':index%6,'students':students,'groups':groups,
                      'pair_agreement':{'CLASS-LOOP':pair_agreement(groups,reference),'no_support':pair_agreement(ablated,reference),
                                        'score_quartile':pair_agreement(score_groups,reference)},
                      'sparse_correct':sparse==detected,'permutation_stable':membership(groups)==membership(dynamic_groups(shuffled,questions)),
                      'task_matches':matching,'runtime_ms':elapsed})
    rows=[c for c in cases if c['split']=='eval'];prototypes=[c for c in rows if c['family'] in [0,1,2,5]]
    return {'evaluation_classes':len(rows),'students':sum(len(c['students']) for c in rows),
            'prototype_classes':len(prototypes),'summary':{m:mean([c['pair_agreement'][m] for c in prototypes]) for m in ['CLASS-LOOP','no_support','score_quartile']},
            'sparse_checks':sum(c['sparse_correct'] for c in rows),'permutation_checks':sum(c['permutation_stable'] for c in rows),
            'task_matches':sum(sum(c['task_matches']) for c in rows),'task_count':sum(len(c['task_matches']) for c in rows),
            'runtime_ms_mean':mean([c['runtime_ms'] for c in rows]),'cases':cases}


def offline():
    for name,function in [('ktrace',ktrace_experiment),('path',path_experiment),('class',class_experiment)]:
        begin=time.perf_counter();data=function();save(name+'.json',data)
        print(name,'complete',round(time.perf_counter()-begin,2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--offline',action='store_true');args=parser.parse_args()
    if args.offline:offline()
