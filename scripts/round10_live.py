"""冻结配对评测，经真实FastAPI、DeepSeek服务和数据库完成。显式运行才计费。"""
from __future__ import annotations
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
OUT=ROOT/'docs/experiments/round10'
from backend.app.ai import AIService, limiter
from backend.app.ai_budget import task_id, ledger


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')


STUDENT=[
    ('concept','请用一个反例帮助我理解{topic}，最后让我独立判断。'),
    ('wrong_step','我做{topic}时跳过了中间状态，结果错了。请先提示怎样找到错误步骤。'),
    ('prerequisite','我对{topic}的基础还不牢，请判断应先补哪一步，再让我验证。'),
    ('hint_dependence','我总是看提示才能完成{topic}的题，请带我做一次减少提示的检查。'),
    ('transfer','把{topic}换一个输入或应用场景，应如何检查方法是否仍成立？'),
    ('attachment','读过课程讲义后，我仍不能区分{topic}的边界，请结合可引用材料解释。'),
    ('video','我刚学习{topic}的视频片段，请用一个简短检查连接视频与实际作答。'),
    ('followup','上次检查没有通过，我把{topic}的条件理解反了，请换一种表征继续辅导。'),
]
TEACHER=[
    ('discussion','讨论{topic}的课堂提问，给出一个能暴露误解的追问。'),
    ('analysis','分析这个班关于{topic}的学情与典型错误，依据实际统计提出可执行建议。'),
    ('mixed','根据这个班{topic}的错误，设计一节30分钟讲评课。'),
    ('lesson','围绕{topic}准备一节20分钟教案，保留独立检查和结果反馈。'),
    ('groups','根据{topic}的薄弱证据安排两组后续练习和25分钟分层教学。'),
    ('question','围绕{topic}设计题目，生成一道单选题并提供答案和解析。'),
    ('rubric','为{topic}的解释型作答设计评分量规，分项总分100，当前未作答，给出0分待教师确认。'),
    ('feedback','依据{topic}的班级错误安排30分钟讲评和后续练习，并说明如何查看完成反馈。'),
]


def freeze(client,headers):
    from backend.app.db import get_db
    with get_db() as db:
        points=[dict(r) for r in db.execute('SELECT id,course_id,title FROM knowledge_points ORDER BY course_id,id')]
    tasks=[]
    for role,patterns in [('student',STUDENT),('teacher',TEACHER)]:
        for family,(kind,template) in enumerate(patterns):
            for repeat in range(5):
                course=1+repeat%2
                pool=[p for p in points if p['course_id']==course]
                point=pool[(family*3+repeat)%len(pool)]
                tasks.append({'id':f'eval-{role}-{family}-{repeat}','split':'eval','role':role,'kind':kind,
                              'model':'deepseek-v4-pro' if repeat==4 and family%2==0 else 'deepseek-flash',
                              'body':{'course_id':course,'knowledge_id':point['id'],
                                      'message':template.format(topic=point['title'])}})
    # Pilot concepts differ from final selection and remain excluded from final denominators.
    for i in range(6):
        role='student' if i<3 else 'teacher'
        template=(STUDENT if role=='student' else TEACHER)[i%3][1]
        point=points[-1-i]
        tasks.insert(i,{'id':f'pilot-{i}','split':'pilot','role':role,'kind':'pilot',
                       'model':'deepseek-flash','body':{'course_id':point['course_id'],'knowledge_id':point['id'],
                       'message':template.format(topic=point['title'])+'请保持简洁。'}})
    protocol={'run_id':'xuemai-r10-20261117-v1','source_commit':os.popen('git rev-parse HEAD').read().strip(),
              'created_at':datetime.now(timezone.utc).isoformat(),'seed':101711,'budget':1000000,
              'model_parameters':{'temperature':.3,'thinking':'disabled','student_max_tokens':700,'teacher_max_tokens':1200},
              'official_pricing_url':'https://api-docs.deepseek.com/quick_start/pricing/',
              'models':{'deepseek-flash':'DeepSeek-V4.1-Flash-1017','deepseek-v4-pro':'DeepSeek-V4-Pro-0813'},
              'conditions':{'full':'原服务的诊断、策略与编排提示',
                            'baseline':'相同上下文、统计、候选、JSON契约与输出预算的单步生成；双方保留同一权限及业务校验'},
              'evaluation':'独立程序检查来源定位、课程对象、理解检查、产物结构、课时、保存和回流；语言量规仅为关键词覆盖代理指标',
              'failure_policy':'所有失败保留，零自动重试；无官方usage按最坏预留扣账；重启跳过已完成结果',
              'tasks':tasks}
    path=OUT/'protocol.json'
    if path.exists():
        return json.loads(path.read_text('utf8'))
    write(path,protocol)
    return protocol


def baseline_messages(messages):
    copied=json.loads(json.dumps(messages))
    system=copied[0]['content']
    # Keep identical evidence and output contracts. Change orchestration phrasing only.
    system=re.sub(r'^.*?\n','你是课程教学助手。依据以下同一份授权材料单步回答，引用使用编号。\n',system,count=1,flags=re.S)
    system=system.replace('结构化诊断与教学策略：','提供的学习记录与候选参考：')
    system=system.replace('教学目标与班级证据：','提供的教学要求与班级原始数据：')
    copied[0]['content']=system
    return copied


def run_case(client,headers,task,condition):
    filename=OUT/'real'/(task['id']+'-'+condition+'.json')
    if filename.exists():
        return json.loads(filename.read_text('utf8'))
    original=AIService.stream
    captured={}
    async def observed(service,messages,**kwargs):
        actual=baseline_messages(messages) if condition=='baseline' else messages
        captured['messages']=actual
        captured['parameters']=service.payload(actual,stream=True,max_tokens=kwargs.get('max_tokens'))
        captured['parameters'].pop('messages',None)
        text=''
        async for fragment in original(service,actual,**kwargs):
            text+=fragment
            yield fragment
        captured['raw_response']=text
    task_id.set(task['id']+'-'+condition)
    # Per-user application limiter remains enabled. Serial experiment pacing honors 30/minute.
    body=task['body']|{'model':task['model']}
    start=time.perf_counter()
    with patch.object(AIService,'stream',observed):
        response=client.post('/api/ai/chat',headers=headers[task['role']],json=body)
    events=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
    done=next((e for e in reversed(events) if e.get('status')=='complete'),{})
    first=events[0] if events else {}
    result={'task':task,'condition':condition,'http_status':response.status_code,'elapsed_seconds':time.perf_counter()-start,
            'api_complete':bool(done),'events':events,**captured}
    if done:
        teaching=done.get('teaching',{});artifact=done.get('artifact',{})
        citations=done.get('citations',first.get('citations',[]))
        result['checks']={'course_and_role':done.get('model',task['model'])==task['model'],
                          'citation_locators':all(c.get('locator') and c.get('version') for c in citations),
                          'has_citation':bool(citations),'has_check':bool(teaching.get('check')),
                          'valid_artifact':bool(artifact.get('id')),
                          'business_status':teaching.get('status')}
        if artifact.get('id') and artifact.get('kind') in ['design','intervention']:
            saved=client.post(f"/api/ai/teacher-drafts/{artifact['id']}/save",headers=headers['teacher'],json=artifact['draft'])
            result['checks']['saved']=saved.status_code==200
        cid=done.get('conversation_id',first.get('conversation_id'))
        if cid:
            history=client.get(f'/api/ai/conversations/{cid}',headers=headers[task['role']]).json()
            result['checks']['persisted']=history.get('messages',[{}])[-1].get('status')=='complete'
    write(filename,result)
    print(task['id'],condition,'complete' if done else 'FAILED',round(result['elapsed_seconds'],2),flush=True)
    return result


def export_ledger():
    with ledger() as db:
        db.row_factory=__import__('sqlite3').Row
        rows=[dict(r) for r in db.execute('SELECT * FROM token_calls WHERE scope=? ORDER BY id',('round10-20261117',))]
    for row in rows:row['usage']=json.loads(row['usage'])
    write(OUT/'token-ledger.json',{'scope':'round10-20261117','limit':1000000,'requests':len(rows),
          'charged_or_reserved':sum(r['reserved'] if r['status']=='reserved' else r['charged'] for r in rows),
          'official_prompt_tokens':sum(r['usage'].get('prompt_tokens',0) for r in rows if not r['usage'].get('estimated',True)),
          'official_completion_tokens':sum(r['usage'].get('completion_tokens',0) for r in rows if not r['usage'].get('estimated',True)),
          'rows':rows})


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--real',action='store_true');parser.add_argument('--pilot-only',action='store_true');args=parser.parse_args()
    if not args.real:raise SystemExit('真实请求需要显式 --real')
    os.environ.update(AI_MODE='real',DATABASE_PATH=str(ROOT/'.local/round10-real.db'),XUEMAI_DEMO_COHORT='1',
                      AI_DEV_BUDGET_SCOPE='round10-20261117',AI_DEV_TOKEN_LIMIT='1000000',
                      AI_BUDGET_DATABASE=str(ROOT/'.local/round10-budget.sqlite'),AI_USAGE_SCOPE='round10-20261117',
                      AI_MAX_TOKENS='1600',AI_TIMEOUT_SECONDS='120',AI_REQUESTS_PER_MINUTE='30')
    from fastapi.testclient import TestClient
    from backend.app.main import app
    with TestClient(app) as client:
        headers={}
        for role,username in [('student','student1'),('teacher','teacher')]:
            auth=client.post('/api/auth/login',json={'username':username,'password':'Xuemai123!'})
            auth.raise_for_status();headers[role]={'Authorization':'Bearer '+auth.json()['token']}
        protocol=freeze(client,headers)
        for task in protocol['tasks']:
            if args.pilot_only and task['split']!='pilot':continue
            # Alternate condition order by fixed ID, preventing a systematic order bias.
            conditions=['full','baseline'] if int(hashlib.sha256(task['id'].encode()).hexdigest(),16)%2 else ['baseline','full']
            for condition in conditions:
                run_case(client,headers,task,condition)
                export_ledger()
                if task['split']=='pilot' and not args.pilot_only:continue
                time.sleep(2.1)
    export_ledger()


if __name__=='__main__':main()
