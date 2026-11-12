"""沿用真实教学与开发素材，更新背景、框架镜头和对应讲稿。"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

import av
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT/'docs/demo/第九轮演示源'
PREVIOUS = ROOT/'docs/demo/第八轮演示源'
LOCAL = ROOT/'.local/round9-edit'


def prepare():
    PROJECT.mkdir(exist_ok=True)
    scenes = json.loads((PREVIOUS/'scenes.json').read_text('utf8'))
    replacements = {
        '问候与介绍':'各位评委老师好，我是西安交通大学软件工程专业的刘嘉程。学脉连接课程学习、个性化辅导与教学协作。',
        '真实教学痛点':'课前要准备材料，课堂需要收集回答，课后还要跟进学习。学生往往不清楚下一步先补什么，教师则要从全班作答中判断谁需要帮助。学脉把资料、活动、辅导和任务关联起来，让每次反馈都能接上后续学习与教学安排。',
        '总体方法框架':'这张图从师生输入出发，汇集课程结构、资料和学习证据。学生侧用知识追踪更新状态，路径规划安排先修与时间，个人辅导检验理解。教师侧依据错因分层，再结合目标编排教学。课程工具与模型服务支持这些操作，师生在各自工作区执行活动，新的作答和反馈继续回流。',
    }
    for scene in scenes:
        scene['text'] = replacements.get(scene['name'], scene['text'])
    (PROJECT/'scenes.json').write_text(json.dumps(scenes,ensure_ascii=False,indent=2),encoding='utf8')
    (ROOT/'scripts/demo-scenes.json').write_text(json.dumps(scenes,ensure_ascii=False,indent=2),encoding='utf8')
    audio = PROJECT/'audio'
    audio.mkdir(exist_ok=True)
    # 缓存仍由文案、声音、语速和WordBoundary设置的摘要核对。
    for source in (PREVIOUS/'audio').glob('r8-*'):
        target = audio/source.name
        if not target.exists():
            shutil.copy2(source,target)


def build():
    prepare()
    LOCAL.mkdir(exist_ok=True)
    media = PROJECT/'media'
    media.mkdir(exist_ok=True)
    for name in ['boards','login','framework']:
        pointer = ROOT/'.local'/('round9-'+name+'-current.json')
        if pointer.exists():
            source = Path(json.loads(pointer.read_text('utf8'))['directory'])
            for filename in ['continuous.webm','continuous.mp4','timeline.json','recording.json','events.json','highlight-audit.json']:
                if (source/filename).exists():
                    shutil.copy2(source/filename,media/(name+'-'+filename))
    rows = json.loads((media/'boards-timeline.json').read_text('utf8'))
    board_rows = {row['name']:row for row in rows}
    amended_framework = media/'framework-timeline.json'
    framework_rows = json.loads(amended_framework.read_text('utf8')) if amended_framework.exists() else []
    timeline = json.loads((PREVIOUS/'edit-timeline.json').read_text('utf8'))
    replacements = {0:'intro',1:'pain',2:'framework',len(timeline['edits'])-1:'outro'}
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    for index, edit in enumerate(timeline['edits']):
        if index == 2 and framework_rows:
            edit['source'] = (media/'framework-continuous.mp4').relative_to(ROOT).as_posix()
            edit['in'] = framework_rows[0]['capture_at']
            edit['out'] = edit['in'] + edit['duration']
        elif index in replacements:
            edit['source'] = (media/'boards-continuous.mp4').relative_to(ROOT).as_posix()
            edit['in'] = board_rows[replacements[index]]['capture_at']
            edit['out'] = edit['in'] + edit['duration']
        elif index == 3:
            edit['source'] = (media/'login-continuous.mp4').relative_to(ROOT).as_posix()
            edit['in'] = .5
            edit['out'] = edit['in'] + edit['duration']
        output = LOCAL/f'clip-{index:02}.mp4'
        subprocess.run([ffmpeg,'-y','-v','error','-ss',str(edit['in']),'-i',str(ROOT/edit['source']),
                        '-an','-frames:v',str(edit['frames']),'-r','30','-c:v','libx264','-preset','veryfast',
                        '-crf','19','-pix_fmt','yuv420p',str(output)],check=True)
    concat = LOCAL/'concat.txt'
    concat.write_text('\n'.join("file '"+(LOCAL/f'clip-{index:02}.mp4').as_posix()+"'" for index in range(len(timeline['edits']))),encoding='utf8')
    output = ROOT/'最终参赛提交材料/学脉XueMai-演示视频.mp4'
    subprocess.run([ffmpeg,'-y','-v','error','-f','concat','-safe','0','-i',str(concat),'-c','copy',
                    '-movflags','+faststart',str(output)],check=True)
    with av.open(str(output)) as video:
        timeline['duration_seconds'] = video.duration/av.time_base
    if not 300 <= timeline['duration_seconds'] <= 480:
        raise ValueError('片长超出官方要求')
    timeline['revision'] = 9
    timeline['framework_regions'] = 'docs/figures/xuemai-framework-regions.json'
    (PROJECT/'edit-timeline.json').write_text(json.dumps(timeline,ensure_ascii=False,indent=2),encoding='utf8')
    print('连续演示剪辑完成',timeline['duration_seconds'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare',action='store_true')
    build() if not parser.parse_args().prepare else prepare()
