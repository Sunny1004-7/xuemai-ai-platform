"""依据稳定场景标识剪辑新连续录屏，核对内容下边界并生成共用字幕布局。"""
import json
from pathlib import Path
import shutil
import subprocess

import av
import imageio_ffmpeg
from PIL import Image, ImageChops, ImageStat

from demo_project import load_project
from media_timeline import validate_clip_range

ROOT = Path(__file__).resolve().parents[1]
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def collect_recording(project, prefix):
    media = project / 'media'
    media.mkdir(exist_ok=True)
    pointer = ROOT / f'.local/round12-{prefix}-current.json'
    if pointer.exists():
        directory = Path(json.loads(pointer.read_text('utf8'))['directory'])
        for path in directory.iterdir():
            if path.is_file() and path.suffix in {'.mp4', '.webm', '.json', '.png'}:
                shutil.copy2(path, media / (prefix + '-' + path.name))
    timeline = json.loads((media / (prefix + '-timeline.json')).read_text('utf8'))
    return timeline


def measure_content(project, prefix, row, screenshot, sample_offset):
    """将同状态视口截图与实际视频逐偏移比较，确认原尺寸与实际位置。"""
    media = project / 'media'
    recording = json.loads((media / (prefix + '-recording.json')).read_text('utf8'))
    initial_viewport = recording['metrics']
    with Image.open(media / (prefix + '-' + screenshot)) as original:
        reference = original.convert('RGB')
    viewport = dict(initial_viewport, width=reference.width, height=reference.height)
    if viewport['width'] != 1920 or viewport['height'] < 900 or viewport['dpr'] != 1 or viewport['zoom'] != '1':
        raise ValueError('稳定画面视口不符合100%缩放要求')
    time = row['capture_at'] + sample_offset
    with av.open(str(media / (prefix + '-continuous.mp4'))) as video:
        video.seek(int(time * av.time_base))
        frame = next(frame for frame in video.decode(video=0) if float(frame.time) >= time)
        actual = frame.to_image()
    width, height = reference.size
    size = (240, round(height / 8))
    reference = reference.resize(size)
    scores = []
    for offset in range(recording['track_settings']['height'] - height + 1):
        sample = actual.crop((0, offset, width, offset + height)).resize(size)
        score = sum(ImageStat.Stat(ImageChops.difference(sample, reference)).mean) / 3
        scores.append((score, offset))
    score, offset = min(scores)
    if width != 1920 or score > 5:
        raise ValueError('实际视频与完整视口截图的原尺寸对应未通过')
    return {'recording': prefix, 'viewport': viewport, 'initial_viewport': initial_viewport, 'native_track_height': recording['track_settings']['height'],
            'matched_top': offset, 'content_bottom': offset + height, 'mean_rgb_error': round(score, 4),
            'sample_time': time, 'reference': prefix + '-' + screenshot}


def main():
    current, number, project = load_project()
    if number != 12:
        raise ValueError('当前工程须为第十二轮')
    scenes = json.loads((project / 'scenes.json').read_text('utf8'))
    modules = collect_recording(project, 'modules')
    boards = collect_recording(project, 'boards')
    if len(modules) != 21 or [row['role'] for row in modules if row['role']!='authentication'] != ['student'] * 10 + ['teacher'] * 9:
        raise ValueError('模块镜头覆盖或身份顺序不正确')
    media = project / 'media'
    if json.loads((media / 'modules-page-errors.json').read_text('utf8')):
        raise ValueError('模块录制存在页面错误')
    observations = [
        measure_content(project, 'modules', next(row for row in modules if row['scene_id']=='student-dashboard'), 'student-dashboard.png', 6),
        measure_content(project, 'boards', next(row for row in boards if row['scene_id'] == 'framework'), 'framework.png', 2),
    ]
    content_bottom = max(observation['content_bottom'] for observation in observations)
    layout = {'width': 1920, 'height': 1080, 'content_bottom': content_bottom,
              'subtitle_region': [content_bottom, 1080], 'subtitle_center': [960, (content_bottom + 1080) / 2],
              'glyph_center_correction': 0, 'observations': observations,
              'method': '实际原生视频与同状态完整视口截图比较，保持画面原尺寸；字幕在共同底部留白中心'}
    previous_layout = project / 'video-layout.json'
    if previous_layout.exists():
        previous = json.loads(previous_layout.read_text('utf8'))
        if previous['content_bottom'] == content_bottom:
            layout['glyph_center_correction'] = previous.get('glyph_center_correction', 0)
    previous_layout.write_text(json.dumps(layout, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    edits = []
    output_frames = 0
    for scene in scenes:
        candidates = [row for row in modules if row['scene_id'] == scene['scene_id']]
        prefix = 'modules'
        if not candidates:
            candidates = [row for row in boards if row['scene_id'] == scene['scene_id']]
            prefix = 'boards'
        if abs(sum(row['duration'] for row in candidates) - scene['duration']) > .001:
            raise ValueError('场景素材长度与讲稿不一致：' + scene['scene_id'])
        within_scene = 0
        for row in candidates:
            frames = round((within_scene + row['duration']) * 30) - round(within_scene * 30)
            validate_clip_range(row,frames/30)
            edit = {'scene_id': scene['scene_id'], 'segment_id': row.get('segment_id', scene['scene_id']),
                    'role': scene['role'], 'module': scene['module'],
                    'category': '系统界面' if prefix == 'modules' else 'AI协同过程复现展示' if scene['role'] == 'development' else '作品介绍',
                    'source': (media / (prefix + '-continuous.mp4')).relative_to(ROOT).as_posix(),
                    'in': row['capture_at'], 'valid_until':row['valid_until'], 'guard_seconds':round(row['valid_until']-row['capture_at']-frames/30,3), 'frames': frames, 'duration': frames / 30, 'start': output_frames / 30}
            edits.append(edit)
            within_scene += row['duration']
            output_frames += frames
    local = ROOT / '.local/round12-edit'
    local.mkdir(exist_ok=True)
    for index, edit in enumerate(edits):
        subprocess.run([FFMPEG, '-y', '-v', 'error', '-ss', str(edit['in']), '-i', str(ROOT / edit['source']),
                        '-an', '-frames:v', str(edit['frames']), '-r', '30', '-c:v', 'libx264', '-threads', '4',
                        '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', str(local / f'clip-{index:02}.mp4')], check=True)
    concat = local / 'concat.txt'
    concat.write_text('\n'.join("file '" + (local / f'clip-{index:02}.mp4').as_posix() + "'" for index in range(len(edits))), encoding='utf8')
    target = project / 'video-unvoiced.mp4'
    subprocess.run([FFMPEG, '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(concat),
                    '-c', 'copy', '-movflags', '+faststart', str(target)], check=True)
    with av.open(str(target)) as video:
        duration = video.duration / av.time_base
    if abs(duration - output_frames / 30) > .05 or not 300 <= duration <= 480:
        raise ValueError('最终片长不符合时间轴')
    timeline = {'revision': 11, 'duration_seconds': duration, 'fps': 30,
                'development_evidence_seconds': sum(edit['duration'] for edit in edits if edit['role'] == 'development'),
                'system_interface_seconds': sum(edit['duration'] for edit in edits if edit['category'] == '系统界面'),
                'edits': edits, 'real_api_calls_new_during_recording': 0, 'real_api_reused': 2,
                'experiment_run_id': 'xuemai-r10-20261117-v1'}
    (project / 'edit-timeline.json').write_text(json.dumps(timeline, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'duration': duration, 'clips': len(edits), 'layout': layout}, ensure_ascii=False))


if __name__ == '__main__':
    main()
