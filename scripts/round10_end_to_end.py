"""20个隔离真实业务场景，共用本轮Token账本，普通执行不发送模型请求。"""
import argparse
import io
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.round10_live import run_case, export_ledger, write, OUT
from backend.app.ai_budget import task_id


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--real',action='store_true');args=parser.parse_args()
    if not args.real:raise SystemExit('付费业务验证需要 --real')
    os.environ.update(AI_MODE='real',DATABASE_PATH=str(ROOT/'.local/round10-e2e.db'),XUEMAI_DEMO_COHORT='1',
        AI_DEV_BUDGET_SCOPE='round10-20261117',AI_DEV_TOKEN_LIMIT='1000000',AI_BUDGET_DATABASE=str(ROOT/'.local/round10-budget.sqlite'),
        AI_USAGE_SCOPE='round10-20261117',AI_MAX_TOKENS='1600',AI_TIMEOUT_SECONDS='120',AI_REQUESTS_PER_MINUTE='30')
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.db import get_db
    from PIL import Image, ImageDraw, ImageFont
    from docx import Document
    import pymupdf
    from backend.app.ai import AIService, selected_config
    results=[]
    with TestClient(app) as client:
        headers={}
        for role,name in [('student','student1'),('teacher','teacher')]:
            headers[role]={'Authorization':'Bearer '+client.post('/api/auth/login',json={'username':name,'password':'Xuemai123!'}).json()['token']}
        for index in range(20):
            path=OUT/'e2e'/f'{index:02}.json'
            if path.exists():results.append(json.loads(path.read_text('utf8')));continue
            cid=1+index%2
            with get_db() as db:
                point=dict(db.execute('SELECT * FROM knowledge_points WHERE course_id=? ORDER BY id LIMIT 1',(cid,)).fetchone())
                question=dict(db.execute("SELECT * FROM questions WHERE course_id=? AND status='approved' AND type='single' ORDER BY id LIMIT 1",(cid,)).fetchone())
            kind=['file','image','teacher_flow','generate','feedback'][index//4]
            checks={};data={};start=time.perf_counter()
            body={'course_id':cid,'knowledge_id':point['id'],'message':f"请结合课程材料解释{point['title']}，给出可执行检查。"}
            role='student';model='deepseek-flash'
            if kind=='file':
                text=f"{point['title']}学习记录：先确认输入、边界和步骤，再用反例检查结论。"
                suffix=['txt','md','docx','pdf'][index%4];raw=text.encode()
                if suffix=='docx':
                    stream=io.BytesIO();doc=Document();doc.add_paragraph(text);doc.save(stream);raw=stream.getvalue()
                if suffix=='pdf':
                    doc=pymupdf.open();page=doc.new_page();page.insert_text((40,50),'Check input, boundary and steps before conclusion.');raw=doc.tobytes()
                uploaded=client.post('/api/ai/attachments',headers=headers[role],data={'course_id':cid},files={'file':('学习记录.'+suffix,raw)})
                checks['uploaded']=uploaded.status_code==201
                if checks['uploaded']:body['attachment_ids']=[uploaded.json()['id']]
                body['message']='根据我上传的学习记录，结合本课程给我一步提示。'
            if kind=='image':
                image=Image.new('RGB',(640,300),'#f4f3eb');draw=ImageDraw.Draw(image)
                draw.text((30,50),'Input [1, 2, 3]\nCheck the last inserted item.\nExplain each operation.',font=ImageFont.truetype('arial.ttf',26),fill='#203f3d')
                stream=io.BytesIO();image.save(stream,format='PNG')
                uploaded=client.post('/api/ai/attachments',headers=headers[role],data={'course_id':cid},files={'file':('操作记录.png',stream.getvalue(),'image/png')})
                checks['uploaded']=uploaded.status_code==201
                body|={'attachment_ids':[uploaded.json()['id']],'message':'请读取图片中的数字和步骤，结合课程给出一个操作顺序检查。'}
            if kind=='teacher_flow':
                role='teacher';body['message']=f"依据这个班{point['title']}的错误，设计30分钟讲评课和分层后续练习。"
                model='deepseek-v4-pro' if index%2 else model
            if kind=='generate':
                role='teacher';generation=['question','lesson','rubric','question'][index%4]
                task_id.set(f'e2e-{index}-generate')
                response=client.post('/api/ai/generate',headers=headers[role],json={'course_id':cid,'knowledge_id':point['id'],
                    'question_id':question['id'],'kind':generation,'prompt':'生成简洁可审核的内容。量规分项总分100，当前作答依据需清晰。','answer':'先确认输入和边界。'})
                checks['generated']=response.status_code==200
                data={'http_status':response.status_code,'result':response.json()}
            else:
                task={'id':f'e2e-{index}','role':role,'kind':kind,'model':model,'split':'business','body':body}
                data=run_case(client,headers,task,'full')
                checks['api_complete']=data['api_complete']
                if data['api_complete']:
                    done=next(e for e in reversed(data['events']) if e.get('status')=='complete')
                    checks['persisted']=data['checks'].get('persisted',False)
                    if kind=='teacher_flow':
                        checks['saved']=data['checks'].get('saved',False)
                        artifact=done.get('artifact',{});groups=artifact.get('draft',{}).get('groups',[])
                        qids=groups[0]['question_ids'] if groups else [question['id']]
                        assignment=client.post('/api/assignments',headers=headers['teacher'],json={'course_id':cid,
                            'title':f'实验讲评复测{index}','question_ids':qids})
                        checks['published']=assignment.status_code==201
                        if checks['published']:
                            aid=assignment.json()['id']
                            scores=[]
                            for qid in qids:
                                with get_db() as db:chosen=dict(db.execute('SELECT * FROM questions WHERE id=?',(qid,)).fetchone())
                                answer=json.loads(chosen['answer'])
                                submitted=client.post('/api/attempts',headers=headers['student'],json={'question_id':qid,'assignment_id':aid,'answer':answer})
                                scores.append(submitted.status_code==201 and submitted.json().get('score')==100)
                            checks['student_scored']=all(scores)
                            returned=client.get(f'/api/assignments/{aid}/results',headers=headers['teacher'])
                            checks['teacher_result']=returned.status_code==200 and any(r['id']==2 and r['completed'] for r in returned.json())
                            data['assignment_id']=aid
                    if kind=='feedback':
                        check=done.get('teaching',{}).get('check')
                        if check:
                            response=client.post(f"/api/ai/checks/{check['id']}/answer",headers=headers['student'],json={'answer':'我需要继续核对边界'})
                            checks['check_recorded']=response.status_code in [200,201]
                        else:checks['check_recorded']=False
            result={'id':index,'kind':kind,'course_id':cid,'checks':checks,'passed':bool(checks) and all(checks.values()),
                    'elapsed_seconds':time.perf_counter()-start,'evidence':data}
            write(path,result);results.append(result);export_ledger()
            print(index,kind,checks,flush=True)
            time.sleep(2.2)
    write(OUT/'end-to-end.json',{'scenarios':len(results),'passed':sum(r['passed'] for r in results),'results':results})
    export_ledger()


if __name__=='__main__':main()
