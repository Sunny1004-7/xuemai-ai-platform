"""从统一讲稿生成整段中文旁白与语义单行字幕。"""
import asyncio
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import wave
import imageio_ffmpeg
from PIL import ImageFont
from subtitle_layout import semantic_lines

ROOT=Path(__file__).resolve().parents[1]
FFMPEG=imageio_ffmpeg.get_ffmpeg_exe()

def duration(path):
    with wave.open(str(path)) as wav:return wav.getnframes()/wav.getframerate()

def timestamp(seconds):
    ms=round(seconds*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'

async def synthesize(round_number=None):
    import edge_tts
    current = json.loads((ROOT/'docs/demo/current.json').read_text('utf8'))
    round_number = round_number or current['round']
    latest = round_number >= 8
    project = ROOT/('docs/demo/' + {7:'第七轮',8:'第八轮',9:'第九轮'}[round_number] + '演示源')
    scene_file = project/'scenes.json'
    scenes=json.loads(scene_file.read_text(encoding='utf-8-sig'))
    output=project/'audio' if latest else ROOT/'.local/narration'
    output.mkdir(exist_ok=True,parents=True)
    voice = 'zh-CN-YunxiNeural' if latest else 'zh-CN-XiaoxiaoNeural'
    rate = '-3%' if latest else '+4%'
    segments=[];subtitles=[]
    font = ImageFont.truetype('msyh.ttc', current['subtitle_font_size']) if round_number == 9 else None
    pacing_issues=[]
    for scene in scenes:
        sentences=[scene['text']] if latest else [s for s in re.split(r'(?<=[。！？；])',scene['text']) if s.strip()]
        waves=[]
        for i,text in enumerate(sentences):
            base=output/f'{scene["id"]}-{i+1:02}'
            mp3=base.with_suffix('.mp3');wav=base.with_suffix('.wav')
            metadata=base.with_suffix('.jsonl');cache=base.with_suffix('.sha256')
            digest=hashlib.sha256((text+'|'+voice+'|'+rate+'|WordBoundary').encode('utf-8')).hexdigest()
            if not (mp3.exists() and metadata.exists() and cache.exists() and cache.read_text('utf-8')==digest):
                await edge_tts.Communicate(text,voice,rate=rate,boundary='WordBoundary').save(str(mp3),str(metadata))
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
        if latest and tempo>1.06:
            pacing_issues.append({'scene':scene['name'],'tempo':round(tempo,4),'text':scene['text']})
        at=scene['start']+.6
        for text,wav,seconds,boundaries in waves:
            if tempo>1.001:
                adjusted=wav.with_name(wav.stem+'-fit.wav')
                subprocess.run([FFMPEG,'-y','-loglevel','error','-i',str(wav),'-filter:a',f'atempo={tempo:.5f}',str(adjusted)],check=True)
                wav=adjusted;seconds=duration(wav)
            segments.append({'scene':scene['name'],'text':text,'start':round(at,3),'duration':round(seconds,3),'file':wav.relative_to(ROOT).as_posix(),'word_boundary_count':len(boundaries),'tempo':round(tempo,5)})
            if round_number == 9:
                clauses = semantic_lines(text, font.getlength)
            else:
                clauses=[];phrase=''
                clauses_source = re.split(r'(?<=[，。！？；：、])',text) if latest else re.split(r'(?<=[，：、])',text)
                for clause in clauses_source:
                    if len(phrase+clause)>27 and phrase:clauses.append(phrase);phrase=''
                    phrase+=clause
                if phrase:clauses.append(phrase)
            cursor=0
            for clause in clauses:
                included=[b for b in boundaries if b['end']>cursor and b['begin']<cursor+len(clause)]
                if not included:raise ValueError('字幕没有对应的词语边界')
                subat=at+included[0]['start']/tempo
                end=at+min(seconds,included[-1]['stop']/tempo+.10)
                subtitles.append({'start':subat,'end':end,'text':clause,
                                  'width':round(font.getlength(clause),2) if font else None})
                cursor+=len(clause)
            at+=seconds+.16
        if at>scene['start']+scene['duration']:raise ValueError('配音超出场景：'+scene['name'])
        print(scene['name'],len(waves),'sentences',round(at-scene['start'],2),'seconds',flush=True)
    if pacing_issues:
        (output/'pacing-issues.json').write_text(json.dumps(pacing_issues,ensure_ascii=False,indent=2),encoding='utf8')
        raise ValueError('有'+str(len(pacing_issues))+'个语段需要调整讲稿或画面时长，详见pacing-issues.json')
    (output/'segments.json').write_text(json.dumps(segments,ensure_ascii=False,indent=2),encoding='utf8')
    for left,right in zip(subtitles,subtitles[1:]):
        left['end']=min(left['end'],right['start']-.02)
    if any(row['end']-row['start'] < .8 for row in subtitles):
        raise ValueError('存在过短字幕，请结合语义合并讲稿片段')
    encoded='\n'.join(f'{index+1}\n{timestamp(row["start"])} --> {timestamp(row["end"])}\n{row["text"]}\n' for index,row in enumerate(subtitles))
    final=ROOT/'最终参赛提交材料';final.mkdir(exist_ok=True)
    (final/'学脉XueMai-演示字幕.srt').write_text(encoded,encoding='utf8')
    (ROOT/'docs/demo').mkdir(exist_ok=True)
    description = '本片采用原生标签页媒体流连续采集，先确定实际画面与剪辑，再制作完整语段旁白。时间轴见第八轮演示源/edit-timeline.json。开场、痛点、框架、界面、开发过程与感谢依次展开。复用两次既有官方请求，本次新增DeepSeek请求0次。三条真实开发档案回放135秒，分别标明2026年11月3日与12日。云希中文神经合成人声按语段生成，字幕使用同次WordBoundary。字幕为透明背景，保留轻描边。完整可编辑源、录屏、边界、音轨和字幕随包提供。' if latest else '原生标签页连续采集，逐句旁白与WordBoundary字幕，实际时间轴见第七轮演示源。'
    if latest:
        (project/'subtitles.srt').write_text(encoded,encoding='utf8')
    if round_number == current['round']:
        (ROOT/'docs/demo/学脉XueMai-演示字幕.srt').write_text(encoded,encoding='utf8')
        (project/'subtitle-layout.json').write_text(json.dumps({'font':current['subtitle_font'],
            'font_size':current['subtitle_font_size'],'measured_max_width':1440,
            'safe_width':current['subtitle_safe_width'],'single_line':True,'cues':subtitles},ensure_ascii=False,indent=2),encoding='utf8')
    description = description.replace('第八轮演示源', project.name)
    (ROOT/'docs/demo/讲解稿与分镜.md').write_text('# 学脉系统演示分镜\n\n'+description+'\n\n'+'\n\n'.join(f'## {s["name"]}（{s["start"]}—{s["start"]+s["duration"]}秒）\n\n{s["text"]}' for s in scenes),encoding='utf8')
    print('完成',len(segments),'语段配音、' if latest else '句配音、',len(subtitles),'条字幕')

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--round',type=int,choices=[7,8,9])
    asyncio.run(synthesize(parser.parse_args().round))
