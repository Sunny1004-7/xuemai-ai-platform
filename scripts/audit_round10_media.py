"""检查当前视频源、字幕、图形边界并导出逐场景与开发档案关键帧。"""
from pathlib import Path
import hashlib
import json
import av
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'docs/demo/第十轮演示源'


def main():
    source=ROOT/'docs/deliverables/xuemai-demo-1080p.mp4'
    scenes=json.loads((PROJECT/'scenes.json').read_text('utf8'))
    timeline=json.loads((PROJECT/'edit-timeline.json').read_text('utf8'))
    phases=json.loads((PROJECT/'framework-phases.json').read_text('utf8'))
    geometry=json.loads((PROJECT/'media/framework-highlight-audit.json').read_text('utf8'))
    points=[(s['name'],s['start']+s['duration']/2) for s in scenes]
    for phase in phases:
        points += [(phase['name']+'-'+stage,30+phase['at']+delta) for stage,delta in [('开始',.08),('淡入',.18),('稳定',.7)]]
    points += [(f'开发原始记录{i}',e['start']+3) for i,e in enumerate(timeline['edits']) if e['category']=='开发过程']
    local=ROOT/'.local/round10-video-frames';local.mkdir(exist_ok=True)
    public=PROJECT/'验收关键帧';public.mkdir(exist_ok=True)
    rows=[]
    for index,(name,at) in enumerate(points):
        with av.open(str(source)) as container:
            stream=container.streams.video[0];container.seek(int(at/stream.time_base),stream=stream)
            for frame in container.decode(stream):
                if frame.time is not None and frame.time>=at:
                    image=frame.to_image();break
        filename=f'{index+1:02}-{name}.png';image.save(public/filename);image.save(local/filename)
        rows.append({'name':name,'at':round(frame.time,3),'file':filename})
    font=ImageFont.truetype('msyh.ttc',18)
    for begin in range(0,len(rows),8):
        sheet=Image.new('RGB',(1920,660),'#e0e4de');draw=ImageDraw.Draw(sheet)
        for i,row in enumerate(rows[begin:begin+8]):
            image=Image.open(local/row['file']);image.thumbnail((475,285));x=i%4*480;y=i//4*330
            sheet.paste(image,(x,y));draw.text((x+4,y+289),f'{row["at"]:.2f}s '+row['name'],font=font,fill='#203f3d')
        sheet.save(local/f'contact-{begin//8+1:02}.jpg',quality=90)
    layout=json.loads((PROJECT/'subtitle-layout.json').read_text('utf8'))
    assert ''.join(c['text'] for c in layout['cues'])==''.join(s['text'] for s in scenes)
    assert all('\n' not in c['text'] and c['width']<=1440 for c in layout['cues'])
    assert (PROJECT/'subtitles.srt').read_bytes()==(ROOT/'docs/demo/学脉XueMai-演示字幕.srt').read_bytes()==(ROOT/'最终参赛提交材料/学脉XueMai-演示字幕.srt').read_bytes()
    assert (PROJECT/'subtitles.ass').read_bytes()==(ROOT/'docs/demo/学脉XueMai-演示字幕.ass').read_bytes()
    assert json.loads((ROOT/'scripts/demo-scenes.json').read_text('utf8'))==scenes
    assert timeline['development_evidence_seconds']>=120
    for phase in geometry:
        box=phase['box']
        for target in phase['targets']:
            margins=[target['left']-box['left'],target['top']-box['top'],box['left']+box['width']-target['left']-target['width'],box['top']+box['height']-target['top']-target['height']]
            assert min(margins)>=phase['padding']-.01
    result={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'frames':len(rows),'frame_points':rows,
            'highlight_groups':len(geometry),'all_targets_contained':True,'subtitle_cues':len(layout['cues']),
            'max_subtitle_width':max(c['width'] for c in layout['cues']),
            'min_subtitle_seconds':min(c['end']-c['start'] for c in layout['cues']),
            'current_copies_identical':True,'human_listening_review':False}
    (ROOT/'docs/rounds/第十轮视频边界与字幕验收.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8',newline='\n')
    print('已导出',len(rows),'帧并核对字幕与语义边界')


if __name__=='__main__':main()
