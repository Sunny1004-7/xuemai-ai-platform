"""显式执行四个正式端点抽样；独立联调账本、零重试，普通测试不导入。"""
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'scripts'))


def main():
    import ai_smoke
    from fastapi.testclient import TestClient
    from backend.app.main import app
    os.environ.update(AI_MODE='real',AI_USAGE_SCOPE='round3-validation',AI_MAX_TOKENS='768',XUEMAI_DEMO_COHORT='0',DATABASE_PATH='.local/live-round3.db')
    ai_smoke.LEDGER=ROOT/'data/ai-smoke-round3.json'
    if ai_smoke.LEDGER.exists():
        raise SystemExit('本轮联调账本已存在，停止重复计费请求；请直接检查已保存报告')
    results=[]
    with TestClient(app) as client:
        def login(username):
            return {'Authorization':'Bearer '+client.post('/api/auth/login',json={'username':username,'password':'Xuemai123!'}).json()['token']}
        student,teacher=login('student1'),login('teacher')
        cases=[('协作辅导','stream','/api/ai/chat',student,{'course_id':1,'knowledge_id':2,'question_id':1,'message':'用一个小例子提示栈与队列的区别，保留理解检查。'}),
               ('智能出题','structured','/api/ai/generate',teacher,{'course_id':1,'knowledge_id':2,'kind':'question','prompt':'一道简短单选题，检验入栈出栈顺序。'}),
               ('辅助备课','structured','/api/ai/generate',teacher,{'course_id':1,'knowledge_id':2,'kind':'lesson','prompt':'一份简短的栈与队列教案，每个数组最多两项。'}),
               ('量规评阅','structured','/api/ai/generate',teacher,{'course_id':1,'question_id':6,'kind':'rubric','prompt':'按已有量规简短评价。','answer':'极端枢轴导致划分不均衡，可以随机选择枢轴。'})]
        for label,kind,path,headers,body in cases:
            number=ai_smoke.reserve(kind)
            response=client.post(path,headers=headers,json=body)
            try:
                if path.endswith('/chat'):
                    block=response.text.split('event: done\ndata: ')[1].split('\n')[0]
                    result=json.loads(block)
                    assert result['teaching']['collaboration']['verification']['passed']
                    assert result['teaching']['check']
                    usage=result.get('usage',{})
                else:
                    result=response.json()
                    assert response.status_code==200 and result['mode']=='real' and result['result']
                    usage=result.get('usage',{})
                ai_smoke.finish(number,'ok',usage)
                results.append({'case':label,'status':'ok','usage':usage})
            except Exception:
                ai_smoke.finish(number,'failed',{},'endpoint_validation')
                results.append({'case':label,'status':'failed','http_status':response.status_code})
                break
    output=ROOT/'docs/rounds/第三轮DeepSeek联调.json'
    output.write_text(json.dumps({'scope':'round3-validation','requests':len(results),'automatic_retries':0,'results':results},ensure_ascii=False,indent=2),'utf-8')
    print(output.read_text('utf-8'))
    if any(r['status']!='ok' for r in results):
        raise SystemExit(1)


if __name__=='__main__':
    if '--run' not in sys.argv:
        raise SystemExit('必须显式使用 --run 才发送计费请求')
    main()
