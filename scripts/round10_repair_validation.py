"""保留初次失败，用原响应离线重放，并用8个新教学任务独立复核。"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.round10_live import run_case,write,export_ledger,OUT


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--real',action='store_true');args=parser.parse_args()
    if not args.real:raise SystemExit('独立真实复核需要 --real')
    os.environ.update(AI_MODE='real',DATABASE_PATH=str(ROOT/'.local/round10-e2e.db'),XUEMAI_DEMO_COHORT='1',
        AI_DEV_BUDGET_SCOPE='round10-20261117',AI_DEV_TOKEN_LIMIT='1000000',AI_BUDGET_DATABASE=str(ROOT/'.local/round10-budget.sqlite'),
        AI_USAGE_SCOPE='round10-20261117',AI_MAX_TOKENS='1600',AI_TIMEOUT_SECONDS='120',AI_REQUESTS_PER_MINUTE='30')
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.db import get_db
    from backend.app.teacher_assistant import finalize_teacher
    from backend.app.ai_routes import ChatInput
    results=[]
    with TestClient(app) as client:
        header={'Authorization':'Bearer '+client.post('/api/auth/login',json={'username':'teacher','password':'Xuemai123!'}).json()['token']}
        for index in [8,11]:
            original=json.loads((OUT/'real'/f'e2e-{index}-full.json').read_text('utf8'))
            done=original['events'][-1];plan=done['teaching']
            request=ChatInput(**(original['task']['body']|{'conversation_id':done['conversation_id'],'request_id':f'format-repair-{index}'}))
            with get_db() as db:
                teacher=dict(db.execute("SELECT * FROM users WHERE username='teacher'").fetchone())
                visible,newplan,artifact=finalize_teacher(db,teacher,request,plan,original['raw_response'],[])
            saved=client.post(f"/api/ai/teacher-drafts/{artifact['id']}/save",headers=header,json=artifact['draft']) if artifact.get('id') else None
            results.append({'original_case':index,'recovered':bool(artifact.get('id')),'saved':saved is not None and saved.status_code==200,
                            'no_new_model_request':True,'artifact':artifact})
        independent=[]
        with get_db() as db:
            points=[dict(r) for r in db.execute('SELECT id,title,course_id FROM knowledge_points WHERE id>=25 ORDER BY id DESC LIMIT 8')]
        for i,point in enumerate(points):
            task={'id':f'repair-independent-{i}','split':'independent-recheck','role':'teacher','kind':'lesson',
                  'model':'deepseek-flash','body':{'course_id':point['course_id'],'knowledge_id':point['id'],
                  'message':f"请为{point['title']}准备一节25分钟教案，依据班级错误设计活动和后续分层练习。"}}
            record=run_case(client,{'teacher':header},task,'full');independent.append({'id':task['id'],'checks':record.get('checks',{}),'api_complete':record['api_complete']})
            export_ledger();time.sleep(2.2)
        write(OUT/'repair-validation.json',{'original_failures':results,'independent_cases':independent,
              'independent_passed':sum(r['api_complete'] and r['checks'].get('valid_artifact') and r['checks'].get('saved') for r in independent)})
    export_ledger()


if __name__=='__main__':main()
