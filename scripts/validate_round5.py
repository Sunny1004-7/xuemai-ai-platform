"""在正常初始化的独立数据库核验双课程覆盖与10/30/60分钟真实推荐。"""
from pathlib import Path
import json, os, sys
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['DATABASE_PATH']=str(ROOT/'.local'/('round5-evidence-'+datetime.now().strftime('%Y%m%d%H%M%S')+'.db'))
os.environ['AI_MODE']='mock'
from backend.app.db import init_db,get_db
from backend.app.learning import recommendations
from scripts.check_content_coverage import inspect
init_db()
with get_db() as db:
    result=inspect(db)
    result['generated_at']=datetime.now(timezone.utc).isoformat()
    result['api_requests']=0
    result['budget_cases']=[]
    user=dict(db.execute('SELECT * FROM users WHERE id=2').fetchone())
    for course in result['courses']:
        for minutes in (10,30,60):
            db.execute("UPDATE learning_goals SET daily_minutes=? WHERE student_id=2 AND course_id=? AND status='active'",(minutes,course['course_id']))
            rec=recommendations(db,user,course['course_id'])
            selected=[r for r in rec if r['in_current_plan']]
            used=sum(r['estimated_minutes'] for r in selected)
            assert rec[0]['path_plan']['budget']==minutes and used<=minutes
            result['budget_cases'].append({'course':course['code'],'budget':minutes,'used':used,'activities':[{'kind':r['kind'],'minutes':r['estimated_minutes'],'title':r['title'],'href':r['href']} for r in selected]})
    assert result['passed'] and not result['foreign_key_errors']
output=ROOT/'docs/rounds/第五轮课程与预算验证.json'
output.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps({'passed':True,'courses':len(result['courses']),'budget_cases':len(result['budget_cases']),'output':str(output)},ensure_ascii=False))
