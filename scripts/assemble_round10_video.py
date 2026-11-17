"""保留连续教学录屏，重录大字画板和真实开发档案的逐阶段回放。"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import av
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'docs/demo/第十轮演示源'
PREVIOUS=ROOT/'docs/demo/第九轮演示源'
LOCAL=ROOT/'.local/round10-edit'


def prepare():
    PROJECT.mkdir(exist_ok=True)
    for filename in ['boards.json','framework-phases.json','product.json']:
        if not (PROJECT/filename).exists():shutil.copy2(PREVIOUS/filename,PROJECT/filename)
    original=json.loads((PREVIOUS/'framework-phases.json').read_text('utf8'))
    for phase in original:phase['at']=round(phase['at']*24/27,3)
    boundary_file=PROJECT/'audio/r8-03-01.jsonl'
    segments_file=PROJECT/'audio/segments.json'
    if boundary_file.exists() and segments_file.exists():
        segment=next(s for s in json.loads(segments_file.read_text('utf8')) if s['scene']=='总体方法框架')
        text=segment['text'];cursor=0;boundaries=[]
        import html
        for line in boundary_file.read_text('utf8').splitlines():
            item=json.loads(line)
            if item.get('type')!='WordBoundary':continue
            word=html.unescape(item['text']);position=text.find(word,cursor)
            boundaries.append((position,position+len(word),item['offset']/1e7));cursor=position+len(word)
        phrases=['这张图','汇集','学生侧','教师侧','课程工具','这些操作','新的作答']
        for phase,phrase in zip(original,phrases):
            position=text.index(phrase)
            at=next(at for begin,end,at in boundaries if begin<=position<end)
            phase|={'at':round(.6+at/segment['tempo'],3),'spoken_phrase':phrase}
    (PROJECT/'framework-phases.json').write_text(json.dumps(original,ensure_ascii=False,indent=2),encoding='utf8',newline='\n')
    summary=json.loads((ROOT/'docs/experiments/round10/summary.json').read_text('utf8'))
    scenes=json.loads((PREVIOUS/'scenes.json').read_text('utf8'))
    scenes[0]|={'duration':14,'text':'各位评委老师好。学生做完一道题，常常知道了答案，却还不清楚下一步该学什么。'}
    scenes[1]|={'duration':16,'text':'教师看到成绩，也需要判断不同学生的困难。围绕这些问题，我们设计了学脉，把课程学习、个性化辅导和教学协作连接在一起。'}
    scenes[2]|={'duration':24,'text':'这张图汇集课程结构、资料和学习证据。学生侧更新知识状态，按照先修与时间安排学习，再通过辅导检验理解。教师侧依据错因分层，结合目标编排教学。课程工具与模型服务支持这些操作，新的作答和反馈继续形成依据。'}
    scenes[15]|={'duration':13.267,'text':'Python课程同样提供知识关系、视频与练习。切换课程后，状态和材料随之更新，学生能够沿相同的方式继续学习。'}
    scenes.insert(16,{'id':'r10-results','name':'同约束方法验证','duration':12,
        'text':f'七百二十种场景，先修与预算违规均为零。相对可行贪心，平均计划效用提高约百分之{summary["path_mean_gain_percent"]:.2f}。'})
    scenes[-1]|={'duration':12,'text':'以上是学脉的主要功能与开发过程，感谢各位评委老师的观看与指导。'}
    at=0
    for scene in scenes:scene['start']=round(at,3);at+=scene['duration']
    (PROJECT/'scenes.json').write_text(json.dumps(scenes,ensure_ascii=False,indent=2),encoding='utf8',newline='\n')
    (ROOT/'scripts/demo-scenes.json').write_text(json.dumps(scenes,ensure_ascii=False,indent=2),encoding='utf8',newline='\n')
    audio=PROJECT/'audio';audio.mkdir(exist_ok=True)
    for source in (PREVIOUS/'audio').glob('*'):
        if source.is_file() and not (audio/source.name).exists():shutil.copy2(source,audio/source.name)
    current=json.loads((ROOT/'docs/demo/current.json').read_text('utf8'))
    current|={'round':10,'project':'docs/demo/第十轮演示源','scenes':'docs/demo/第十轮演示源/scenes.json','assembler':'scripts/assemble_round10_video.py'}
    (ROOT/'docs/demo/current.json').write_text(json.dumps(current,ensure_ascii=False,indent=2),encoding='utf8',newline='\n')


def build():
    prepare();LOCAL.mkdir(exist_ok=True);media=PROJECT/'media';media.mkdir(exist_ok=True)
    pointer=json.loads((ROOT/'.local/round10-boards-current.json').read_text('utf8'))
    recorded=Path(pointer['directory'])
    for name in ['continuous.mp4','continuous.webm','timeline.json','recording.json','events.json','highlight-audit.json']:
        if (recorded/name).exists():shutil.copy2(recorded/name,media/('boards-'+name))
    board_rows={str(r['name']):r for r in json.loads((media/'boards-timeline.json').read_text('utf8'))}
    framework_pointer=ROOT/'.local/round10-framework-current.json'
    framework_row=None
    if framework_pointer.exists():
        framework=Path(json.loads(framework_pointer.read_text('utf8'))['directory'])
        for name in ['continuous.mp4','continuous.webm','timeline.json','recording.json','events.json','highlight-audit.json']:
            if (framework/name).exists():shutil.copy2(framework/name,media/('framework-'+name))
        framework_row=json.loads((media/'framework-timeline.json').read_text('utf8'))[0]
    old=json.loads((PREVIOUS/'edit-timeline.json').read_text('utf8'));edits=[]
    for index,edit in enumerate(old['edits']):
        edit=edit.copy()
        if index in [0,1,2,len(old['edits'])-1]:
            name={0:'intro',1:'pain',2:'framework',len(old['edits'])-1:'outro'}[index]
            edit|={'source':(media/'boards-continuous.mp4').relative_to(ROOT).as_posix(),
                   'in':board_rows[name]['capture_at'],'duration':{'intro':14,'pain':16,'framework':24,'outro':12}[name]}
            if index==2 and framework_row:
                edit|={'source':(media/'framework-continuous.mp4').relative_to(ROOT).as_posix(),'in':framework_row['capture_at']}
        elif edit['category']=='开发过程':
            position=sum(e['category']=='开发过程' for e in edits)
            edit|={'source':(media/'boards-continuous.mp4').relative_to(ROOT).as_posix(),'in':board_rows[str(position)]['capture_at']}
        if index==13:
            # Preserve the complete Python scene. Use its latter duration for a new evidence board.
            edit['duration']=13.266666666666667
        edit['frames']=round(edit['duration']*30);edit['duration']=edit['frames']/30
        edits.append(edit)
        if index==13:
            edits.append({'source':(media/'boards-continuous.mp4').relative_to(ROOT).as_posix(),
                'in':board_rows['results']['capture_at'],'duration':12,'frames':360,'category':'作品说明'})
    at=0;ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    for i,edit in enumerate(edits):
        edit['start']=at;edit['out']=edit['in']+edit['duration'];at+=edit['duration']
        subprocess.run([ffmpeg,'-y','-v','error','-ss',str(edit['in']),'-i',str(ROOT/edit['source']),'-an',
            '-frames:v',str(edit['frames']),'-r','30','-c:v','libx264','-preset','veryfast','-crf','19','-pix_fmt','yuv420p',str(LOCAL/f'clip-{i:02}.mp4')],check=True)
    concat=LOCAL/'concat.txt';concat.write_text('\n'.join("file '"+(LOCAL/f'clip-{i:02}.mp4').as_posix()+"'" for i in range(len(edits))),encoding='utf8',newline='\n')
    target=ROOT/'最终参赛提交材料/学脉XueMai-演示视频.mp4'
    subprocess.run([ffmpeg,'-y','-v','error','-f','concat','-safe','0','-i',str(concat),'-c','copy','-movflags','+faststart',str(target)],check=True)
    with av.open(str(target)) as source:duration=source.duration/av.time_base
    if not 300<=duration<=480:raise ValueError('片长超限')
    timeline={'revision':10,'duration_seconds':duration,'fps':30,'development_evidence_seconds':135,
        'system_interface_seconds':sum(e['duration'] for e in edits if e['category']=='系统界面'),'edits':edits,
        'real_api_calls_new_during_recording':0,'real_api_reused':2,'experiment_run_id':'xuemai-r10-20261117-v1'}
    (PROJECT/'edit-timeline.json').write_text(json.dumps(timeline,ensure_ascii=False,indent=2),encoding='utf8',newline='\n')
    print('连续录屏剪辑完成',duration)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true')
    prepare() if parser.parse_args().prepare else build()
