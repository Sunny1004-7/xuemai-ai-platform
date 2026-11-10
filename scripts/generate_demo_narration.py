"""生成逐句中文配音、准确到句的字幕和可复用音轨。"""
import asyncio
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
            if not mp3.exists():
                await edge_tts.Communicate(text,'zh-CN-XiaoxiaoNeural',rate='+4%').save(str(mp3))
            subprocess.run([FFMPEG,'-y','-loglevel','error','-i',str(mp3),'-ar','24000','-ac','1',str(wav)],check=True)
            waves.append((text,wav,duration(wav)))
        required=sum(s for _,_,s in waves)+.16*(len(waves)-1)
        available=scene['duration']-1.3
        tempo=max(1,required/available)
        at=scene['start']+.6
        for text,wav,seconds in waves:
            if tempo>1.001:
                adjusted=wav.with_name(wav.stem+'-fit.wav')
                subprocess.run([FFMPEG,'-y','-loglevel','error','-i',str(wav),'-filter:a',f'atempo={tempo:.5f}',str(adjusted)],check=True)
                wav=adjusted;seconds=duration(wav)
            segments.append({'scene':scene['name'],'text':text,'start':round(at,3),'duration':round(seconds,3),'file':wav.relative_to(ROOT).as_posix()})
            clauses=[];current=''
            for clause in re.split(r'(?<=[，：、])',text):
                if len(current+clause)>27 and current:clauses.append(current);current=''
                current+=clause
            if current:clauses.append(current)
            total=sum(len(s) for s in clauses);subat=at
            for clause in clauses:
                end=subat+seconds*len(clause)/total
                subtitles.append(f'{len(subtitles)+1}\n{timestamp(subat)} --> {timestamp(end)}\n{clause}\n')
                subat=end
            at+=seconds+.16
        if at>scene['start']+scene['duration']:raise ValueError('配音超出场景：'+scene['name'])
        print(scene['name'],len(waves),'sentences',round(at-scene['start'],2),'seconds',flush=True)
    (output/'segments.json').write_text(json.dumps(segments,ensure_ascii=False,indent=2),encoding='utf8')
    final=ROOT/'最终参赛提交材料';final.mkdir(exist_ok=True)
    (final/'学脉XueMai-演示字幕.srt').write_text('\n'.join(subtitles),encoding='utf8')
    (ROOT/'docs/demo').mkdir(exist_ok=True)
    (ROOT/'docs/demo/讲解稿与分镜.md').write_text('# 学脉系统演示分镜\n\n总时长7分钟，1920×1080。0:00—4:40展示系统操作，4:40—6:50回放三组原始协作与当前方法，最后10秒为片尾。配音采用晓晓中文合成语音，逐句生成，底部字幕与每句音轨同步。系统操作使用隔离数据库和本地示例模式。\n\n'+'\n\n'.join(f'## {s["name"]}（{s["start"]}—{s["start"]+s["duration"]}秒）\n\n{s["text"]}' for s in scenes),encoding='utf8')
    print('完成',len(segments),'句配音、',len(subtitles),'条字幕')

if __name__=='__main__':asyncio.run(synthesize())
