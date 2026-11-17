"""按知识主题分组冻结的200问，三课程真实索引与私有附件检索。"""
from pathlib import Path
import json
import os
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(AI_MODE='mock',DATABASE_PATH=str(ROOT/'.local/round10-retrieval.db'),XUEMAI_DEMO_COHORT='1')
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_db
from backend.app.retrieval import retrieve,sync_index

OUT=ROOT/'docs/experiments/round10'


def main():
    if (OUT/'retrieval.json').exists():
        print('已存在冻结结果，跳过重复构造');return
    with TestClient(app) as client:
        teacher={'Authorization':'Bearer '+client.post('/api/auth/login',json={'username':'teacher','password':'Xuemai123!'}).json()['token']}
        student={'Authorization':'Bearer '+client.post('/api/auth/login',json={'username':'student1','password':'Xuemai123!'}).json()['token']}
        def post(url,body):
            response=client.post('/api'+url,headers=teacher,json=body);response.raise_for_status();return response.json()
        course=post('/courses',{'title':'信息素养实验单元','description':'来源、时间、对象和证据的交叉核验'})
        klass=post('/classes',{'course_id':course['id'],'name':'独立检索验证班'})
        client.post('/api/classes/join',headers=student,json={'join_code':klass['join_code']}).raise_for_status()
        chapter=post(f"/courses/{course['id']}/chapters",{'title':'证据核验'})
        topics=['原始来源','独立证据','发布日期','证据链','样本代表性','相关与因果','图像出处','统计口径','事实与观点','交叉核验']
        for topic in topics:
            point=post(f"/courses/{course['id']}/knowledge",{'title':topic,'chapter_id':chapter['id'],'description':f'判断{topic}需要检查信息来源和适用条件。'})
            post('/resources',{'course_id':course['id'],'knowledge_id':point['id'],'kind':'document',
                              'title':topic+'核验讲义','content':f'# {topic}\n\n{topic}要求追溯原始记录、核对时间和对象，再用独立来源检查结论。多个转载可能共享同一条证据链。\n\n核验步骤：记录发布者、采集时间、统计范围和支持材料，区分事实与推断。'})
        with get_db() as db:
            points=[]
            for cid in [1,2,course['id']]:
                limit=10 if cid==course['id'] else 20
                points += [dict(r) for r in db.execute('''SELECT k.id,k.course_id,k.title,
                    r.id resource_id,r.content FROM knowledge_points k JOIN resources r ON r.knowledge_id=k.id
                    WHERE k.course_id=? AND r.kind='document' GROUP BY k.id ORDER BY k.id LIMIT ?''',(cid,limit))]
            user=dict(db.execute("SELECT * FROM users WHERE username='student1'").fetchone())
            teacher_user=dict(db.execute("SELECT * FROM users WHERE username='teacher'").fetchone())
        cases=[]
        for index,p in enumerate(points):
            content=p['content'];body=next((line for line in content.splitlines() if len(line)>20 and not line.startswith('#')),content)
            phrase=body[:22]
            attachment=client.post('/api/ai/attachments',headers=student,data={'course_id':p['course_id']},
                       files={'file':('核验笔记.md',f"关于{p['title']}的观察记录。{body[:240]}\n\n独立记录标记证据{index:02d}。".encode(),'text/markdown')}).json()
            templates=[('direct',f"{p['title']}的基本定义和关键条件是什么？",p['id'],[],{p['resource_id']}),
                       ('no_knowledge',f"材料中提到“{phrase}”，这一步应怎样理解？",None,[],{p['resource_id']}),
                       ('contrast',f"比较{p['title']}成立与不成立的条件，哪些边界需要核对？",p['id'],[],{p['resource_id']}),
                       ('attachment',f"根据我的笔记解释{p['title']}，核对独立记录标记证据{index:02d}。",None,[attachment['id']],set())]
            for kind,query,kid,aids,reference in templates:
                rows={}
                with get_db() as db:
                    sync_index(db)
                    for method in ['lexical','knowledge','full']:
                        start=time.perf_counter()
                        kwargs={'user':user,'attachment_ids':aids,'knowledge_boost':method!='lexical'}
                        if method!='full':
                            with patch('backend.app.retrieval.ordering_concepts',return_value=set()):
                                found=retrieve(db,p['course_id'],query,kid,**kwargs)
                        else:found=retrieve(db,p['course_id'],query,kid,**kwargs)
                        relevant=[i+1 for i,r in enumerate(found) if
                                  (r.get('resource_id') in reference if kind!='attachment' else r.get('attachment_id') in aids)]
                        rows[method]={'recall_at_1':bool(relevant and min(relevant)<=1),
                                      'recall_at_3':bool(relevant and min(relevant)<=3),'recall_at_5':bool(relevant),
                                      'reciprocal_rank':1/min(relevant) if relevant else 0,
                                      'locator_valid':all(r.get('locator') and r.get('version') for r in found),
                                      'runtime_ms':(time.perf_counter()-start)*1000,'results':found}
                cases.append({'id':f'retrieval-{index}-{kind}','split':'dev' if index%10==0 else 'eval',
                              'topic':p['title'],'course_id':p['course_id'],'query':query,'knowledge_id':kid,
                              'reference_resource_ids':sorted(reference),'reference_attachment_ids':aids,
                              'required_excerpt':body[:100],'kind':kind,'outcomes':rows})
        permission=[]
        with get_db() as db:
            for cid in [1,2,course['id']]:
                rid=db.execute("INSERT INTO resources(course_id,title,kind,content,metadata) VALUES(?,'教师私有核验','document','私有口令鳞羽课后答案','{\"visibility\":\"teacher\"}')",(cid,)).lastrowid
                for role,identity in [('student',user),('teacher',teacher_user)]:
                    found=retrieve(db,cid,'鳞羽课后答案',user=identity)
                    permission.append({'course':cid,'role':role,'private_visible':any(r.get('resource_id')==rid for r in found),
                                       'passed':any(r.get('resource_id')==rid for r in found)==(role=='teacher')})
            empty=retrieve(db,course['id'],'ZXQ729无关的量子通量服务器崩溃')
        evaluated=[c for c in cases if c['split']=='eval']
        summary={m:{k:sum(c['outcomes'][m][k] for c in evaluated)/len(evaluated) for k in
                   ['recall_at_1','recall_at_3','recall_at_5','reciprocal_rank','locator_valid','runtime_ms']}
                 for m in ['lexical','knowledge','full']}
        output={'dataset':'r10-retrieval-v1','group_split':'按知识主题分组，所有改写位于同一分区',
                'total_cases':len(cases),'evaluation_cases':len(evaluated),'courses':3,'summary':summary,
                'permission':permission,'insufficient_evidence_empty':not empty,'cases':cases}
        OUT.mkdir(exist_ok=True,parents=True);(OUT/'retrieval.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({k:v for k,v in output.items() if k!='cases'},ensure_ascii=False))


if __name__=='__main__':main()
