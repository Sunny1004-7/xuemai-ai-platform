"""生成逐句中文配音、准确到句的字幕和可复用音轨。"""
import asyncio
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import wave
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
FFMPEG=imageio_ffmpeg.get_ffmpeg_exe()

def duration(path):
    with wave.open(str(path)) as wav:return wav.getnframes()/wav.getframerate()

def timestamp(seconds):
    ms=round(seconds*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'

async def synthesize():
    import edge_tts
    scenes=json.loads((ROOT/'scripts/demo-scenes.json').read_text(encoding='utf-8-sig'))
    output=ROOT/'.local/narration';output.mkdir(exist_ok=True,parents=True)
    segments=[];subtitles=[]
    for scene in scenes:
        sentences=[s for s in re.split(r'(?<=[。！？；])',scene['text']) if s.strip()]
        waves=[]
        for i,text in enumerate(sentences):
            base=output/f'{scene["id"]}-{i+1:02}'
            mp3=base.with_suffix('.mp3');wav=base.with_suffix('.wav')
            metadata=base.with_suffix('.jsonl');cache=base.with_suffix('.sha256')
            digest=hashlib.sha256((text+'|zh-CN-XiaoxiaoNeural|+4%|WordBoundary').encode('utf-8')).hexdigest()
            if not (mp3.exists() and metadata.exists() and cache.exists() and cache.read_text('utf-8')==digest):
                await edge_tts.Communicate(text,'zh-CN-XiaoxiaoNeural',rate='+4%',boundary='WordBoundary').save(str(mp3),str(metadata))
                cache.write_text(digest,'utf-8')
            subprocess.run([FFMPEG,'-y','-loglevel','error','-i',str(mp3),'-ar','24000','-ac','1',str(wav)],check=True)
            boundaries=[];cursor=0
            for line in metadata.read_text('utf-8').splitlines():
                item=json.loads(line)
                if item.get('type')!='WordBoundary':continue
                word=html.unescape(item['text']);position=text.find(word,cursor)
                if position<0:raise ValueError('语音边界与原文不匹配：'+word)
                boundaries.append({'begin':position,'end':position+len(word),'start':item['offset']/1e7,'stop':(item['offset']+item['duration'])/1e7})
                cursor=position+len(word)
            if not boundaries:raise ValueError('缺少同次合成的词语边界')
            waves.append((text,wav,duration(wav),boundaries))
        required=sum(s for _,_,s,_ in waves)+.16*(len(waves)-1)
        available=scene['duration']-1.3
        tempo=max(1,required/available)
        at=scene['start']+.6
        for text,wav,seconds,boundaries in waves:
            if tempo>1.001:
                adjusted=wav.with_name(wav.stem+'-fit.wav')
                subprocess.run([FFMPEG,'-y','-loglevel','error','-i',str(wav),'-filter:a',f'atempo={tempo:.5f}',str(adjusted)],check=True)
                wav=adjusted;seconds=duration(wav)
            segments.append({'scene':scene['name'],'text':text,'start':round(at,3),'duration':round(seconds,3),'file':wav.relative_to(ROOT).as_posix(),'word_boundary_count':len(boundaries),'tempo':round(tempo,5)})
            clauses=[];current=''
            for clause in re.split(r'(?<=[，：、])',text):
                if len(current+clause)>27 and current:clauses.append(current);current=''
                current+=clause
            if current:clauses.append(current)
            cursor=0
            for clause in clauses:
                included=[b for b in boundaries if b['end']>cursor and b['begin']<cursor+len(clause)]
                if not included:raise ValueError('字幕没有对应的词语边界')
                subat=at+included[0]['start']/tempo
                end=at+min(seconds,included[-1]['stop']/tempo+.10)
                subtitles.append(f'{len(subtitles)+1}\n{timestamp(subat)} --> {timestamp(end)}\n{clause}\n')
                cursor+=len(clause)
            at+=seconds+.16
        if at>scene['start']+scene['duration']:raise ValueError('配音超出场景：'+scene['name'])
        print(scene['name'],len(waves),'sentences',round(at-scene['start'],2),'seconds',flush=True)
    (output/'segments.json').write_text(json.dumps(segments,ensure_ascii=False,indent=2),encoding='utf8')
    final=ROOT/'最终参赛提交材料';final.mkdir(exist_ok=True)
    (final/'学脉XueMai-演示字幕.srt').write_text('\n'.join(subtitles),encoding='utf8')
    (ROOT/'docs/demo').mkdir(exist_ok=True)
    (ROOT/'docs/demo/讲解稿与分镜.md').write_text('# 学脉系统演示分镜\n\n总时长7分30秒，1920×1080。0:00—4:40展示系统操作，4:40—6:40回放三组原始AI协作记录，6:40—7:20说明四项方法与合成机制实验，最后10秒为片尾。配音采用晓晓中文神经合成语音，逐句生成；底部字幕读取同次合成的WordBoundary，随音频适配速度一同换算时间。系统操作使用隔离数据库和本地示例模式。音频缓存以完整文案、声音、语速和边界方式的摘要匹配，修改文案后重新生成。\n\n'+'\n\n'.join(f'## {s["name"]}（{s["start"]}—{s["start"]+s["duration"]}秒）\n\n{s["text"]}' for s in scenes),encoding='utf8')
    print('完成',len(segments),'句配音、',len(subtitles),'条字幕')

if __name__=='__main__':asyncio.run(synthesize())
