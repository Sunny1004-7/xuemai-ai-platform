"""隔离课程材料的片段检索对照，不调用模型。"""
import json
import os
from pathlib import Path
import tempfile

from backend.app.db import init_db,get_db
from backend.app.retrieval import retrieve

def main():
    with tempfile.TemporaryDirectory(prefix='xuemai-r6-method-') as directory:
        os.environ['DATABASE_PATH']=str(Path(directory)/'methods.db')
        os.environ['AI_MODE']='mock'
        os.environ['XUEMAI_DEMO_COHORT']='1'
        init_db()
        cases=[]
        with get_db() as db:
            for course_id in (1,2):
                points=db.execute('SELECT id,title FROM knowledge_points WHERE course_id=? ORDER BY id LIMIT 10',(course_id,)).fetchall()
                for point in points:
                    query='请结合当前知识点，说明边界条件与操作步骤'
                    baseline=retrieve(db,course_id,query,point['id'],user={'id':2,'role':'student'},knowledge_boost=False)
                    enhanced=retrieve(db,course_id,query,point['id'],user={'id':2,'role':'student'},knowledge_boost=True)
                    expected={row[0] for row in db.execute('SELECT id FROM resources WHERE course_id=? AND knowledge_id=?',(course_id,point['id']))}
                    cases.append({'course_id':course_id,'knowledge_id':point['id'],'knowledge':point['title'],'query':query,
                        'keyword_top1':bool(baseline and baseline[0].get('resource_id') in expected),
                        'associated_top1':bool(enhanced and enhanced[0].get('resource_id') in expected),
                        'keyword_top3':any(item.get('resource_id') in expected for item in baseline[:3]),
                        'associated_top3':any(item.get('resource_id') in expected for item in enhanced[:3]),
                        'source_locators_valid':all(item.get('locator') and item.get('version') for item in enhanced),
                        'keyword_titles':[item['title'] for item in baseline[:3]],'associated_titles':[item['title'] for item in enhanced[:3]]})
        report={'conditions':'20个带当前知识点上下文的模糊提问，双课相同材料、分段与候选集合，仅改变知识关联排序项。目标来源是当前知识点关联的课程资料。',
            'cases':cases,'count':len(cases),'keyword_top1_hits':sum(item['keyword_top1'] for item in cases),
            'associated_top1_hits':sum(item['associated_top1'] for item in cases),'keyword_top3_hits':sum(item['keyword_top3'] for item in cases),
            'associated_top3_hits':sum(item['associated_top3'] for item in cases),'locators_valid':all(item['source_locators_valid'] for item in cases),'model_requests':0}
        target=Path('docs/rounds/第六轮检索方法对照.json')
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({key:value for key,value in report.items() if key!='cases'},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
