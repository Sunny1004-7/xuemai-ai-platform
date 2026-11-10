"""隔离合成案例的机制对照；不估计真实学生的学习效果。"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.evidence import estimate_state, update_state
from backend.app.path_planner import plan_path
from backend.app.learning_insights import learning_snapshot, dynamic_groups
from backend.app.db import init_db, get_db


def main():
    now=datetime(2026,11,10,tzinfo=timezone.utc)
    state=estimate_state(now=now)
    independent=update_state(state,True,2,0,now=now)
    correlated=update_state(state,True,2,0,now=now,peer_count=8)
    hinted=update_state(state,True,2,2,now=now)
    ktrace={'independent_weight':independent['weight'],'eight_correlated_variants_weight':round(correlated['weight'],5),
            'independent_posterior':round(independent['value'],5),'hinted_posterior':round(hinted['value'],5),
            'partial_65_quality':update_state(state,True,2,0,now=now,score=65)['quality']}
    scenarios=0;violations=0;baseline_violations=0
    for goal in range(1,7):
        for budget in [8,16,24,32]:
            scenarios+=1
            parents={1:[],2:[1],3:[1],4:[2],5:[3],6:[4,5]}
            states={i:state for i in parents}
            candidates=[{'knowledge_id':i,'estimated_minutes':8,'goal':i==goal} for i in parents]
            plan=plan_path(candidates,parents,states,budget)
            seen=set()
            for kid in plan['knowledge_ids']:
                violations+=int(any(p not in seen for p in parents[kid]));seen.add(kid)
            assert plan['minutes']<=budget
            baseline=sorted(candidates,key=lambda c:(not c['goal'],c['knowledge_id']))[:budget//8]
            seen=set()
            for c in baseline:
                baseline_violations+=int(any(p not in seen for p in parents[c['knowledge_id']]));seen.add(c['knowledge_id'])
    with tempfile.TemporaryDirectory(prefix='xuemai-v3-') as directory:
        os.environ.update(DATABASE_PATH=str(Path(directory)/'validation.db'),AI_MODE='mock',XUEMAI_DEMO_COHORT='1')
        init_db()
        with get_db() as db:
            members=[r[0] for r in db.execute('SELECT student_id FROM class_members WHERE class_id=1')]
            statements=[]
            db.set_trace_callback(statements.append)
            start=time.perf_counter();snapshot=learning_snapshot(db,1,members);elapsed=(time.perf_counter()-start)*1000
            db.set_trace_callback(None)
            questions=[dict(r) for r in db.execute("SELECT * FROM questions WHERE course_id=1 AND status='approved'")]
            groups=dynamic_groups(snapshot['students'],questions)
            cohort={'students':len(members),'graded_attempts':snapshot['summary']['attempt_count'],
                    'distinct_accuracies':len({s['accuracy'] for s in snapshot['students']}),
                    'snapshot_selects':len([q for q in statements if q.startswith('SELECT')]),'snapshot_ms':round(elapsed,2),
                    'group_sizes':[len(g['student_ids']) for g in groups],
                    'average_group_distance':round(sum(g['dispersion']*len(g['student_ids']) for g in groups)/len(members),3)}
    output={'data':'固定种子生成的隔离教学样本','real_ai_requests':0,'K-TRACE':ktrace,
            'PATH-G':{'cases':scenarios,'prerequisite_violations':violations,'static_sort_violations':baseline_violations,'budget_violations':0},
            'CLASS-LOOP':cohort,'DIA-GUIDE':{'verified_by':'backend/tests/test_algorithms_v3.py::test_diaguide_persists_three_roles_and_adapts_after_failed_check','roles':3,'model_calls_per_turn_limit':1,'feedback_changes_strategy':True}}
    (ROOT/'docs/rounds/第三轮核心方法对照.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(output,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
