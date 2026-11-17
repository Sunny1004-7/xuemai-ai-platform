"""实际本地转写后进入真实课程问答，并检查Flash/Pro逐条切换。"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.round10_live import run_case,write,export_ledger,OUT


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--real',action='store_true');args=parser.parse_args()
    if not args.real:raise SystemExit('真实问答需要 --real')
    if (OUT/'voice-and-models.json').exists():return
    os.environ.update(AI_MODE='real',DATABASE_PATH=str(ROOT/'.local/round10-voice.db'),XUEMAI_DEMO_COHORT='1',
        AI_DEV_BUDGET_SCOPE='round10-20261117',AI_DEV_TOKEN_LIMIT='1000000',AI_BUDGET_DATABASE=str(ROOT/'.local/round10-budget.sqlite'),
        AI_USAGE_SCOPE='round10-20261117',AI_MAX_TOKENS='1600',AI_TIMEOUT_SECONDS='120',AI_REQUESTS_PER_MINUTE='30')
    import edge_tts
    audio=OUT/'voice-input.mp3'
    if not audio.exists():asyncio.run(edge_tts.Communicate('我不明白栈和队列的取出顺序有什么区别，请给我一个简单的反例。','zh-CN-YunxiNeural',rate='-3%').save(str(audio)))
    from fastapi.testclient import TestClient
    from backend.app.main import app
    with TestClient(app) as client:
        header={'Authorization':'Bearer '+client.post('/api/auth/login',json={'username':'student1','password':'Xuemai123!'}).json()['token']}
        response=client.post('/api/ai/voice/transcribe',headers=header,files={'file':('提问.mp3',audio.read_bytes(),'audio/mpeg')})
        response.raise_for_status();transcript=response.json()
        results=[]
        for index,model in enumerate(['deepseek-flash','deepseek-v4-pro']):
            task={'id':f'voice-model-{index}','split':'input-business','role':'student','kind':'voice-model-switch',
                  'model':model,'body':{'course_id':1,'knowledge_id':2,'message':transcript['text']}}
            data=run_case(client,{'student':header},task,'full')
            results.append({'model':model,'api_complete':data['api_complete'],'checks':data.get('checks')})
            export_ledger()
        write(OUT/'voice-and-models.json',{'audio_text':'我不明白栈和队列的取出顺序有什么区别，请给我一个简单的反例。',
              'transcription':transcript,'local_transcription':True,'scenarios':2,'results':results})
    export_ledger()


if __name__=='__main__':main()
