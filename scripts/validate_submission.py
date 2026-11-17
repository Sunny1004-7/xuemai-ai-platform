"""检查正式目录的PDF与有声MP4，更新工程内的材料记录。"""
import json
from pathlib import Path
import shutil

import av
import pymupdf

from demo_project import load_project

ROOT = Path(__file__).resolve().parents[1]


def main():
    current, number, project = load_project()
    final = ROOT / '最终参赛提交材料'
    expected = {'学脉XueMai-技术文档.pdf', '学脉XueMai-演示视频-含旁白.mp4',
                '学脉XueMai-完整源码.zip', '学脉XueMai-AI协同开发记录.zip', 'README.md', 'Git演进记录.txt'}
    actual = {path.name for path in final.iterdir() if path.is_file()}
    if actual != expected or any(path.is_dir() for path in final.iterdir()):
        raise ValueError('正式提交目录应包含源码ZIP、AI记录ZIP、README、Git日志、PDF和唯一的有声MP4')
    if {path.name for path in final.glob('*.mp4')} != {'学脉XueMai-演示视频-含旁白.mp4'}:
        raise ValueError('正式提交目录只保留一个有声演示视频版本')
    document = pymupdf.open(final / '学脉XueMai-技术文档.pdf')
    if len(document) > 30:
        raise ValueError('技术报告超过30页')
    with av.open(str(final / '学脉XueMai-演示视频-含旁白.mp4')) as video:
        duration = video.duration / av.time_base
        stream = video.streams.video[0]
        if (stream.width, stream.height, float(stream.average_rate)) != (1920, 1080, 30):
            raise ValueError('视频尺寸或帧率无效')
        if not video.streams.audio or not 300 <= duration <= 480:
            raise ValueError('视频需包含人声且片长为5至8分钟')
    timeline = json.loads((project / 'edit-timeline.json').read_text('utf8'))
    if timeline['development_evidence_seconds'] < 120:
        raise ValueError('AI协同过程展示不足两分钟')
    voices = json.loads((project / 'audio/segments.json').read_text('utf8'))
    subtitles = json.loads((project / 'subtitle-layout.json').read_text('utf8'))
    facts = json.loads((ROOT / 'docs/submission-facts.json').read_text('utf8'))
    facts['delivery'].update(pdf_pages=len(document), video_seconds=round(duration, 3),
        development_seconds=timeline['development_evidence_seconds'],
        system_ui_seconds=timeline['system_interface_seconds'],
        voice_paragraphs=len(voices), subtitles=len(subtitles['cues']))
    facts['delivery']['screenshots_scope'] = '沿用既有界面图，本轮按用户要求取消全量截图'
    facts['delivery'].pop('visual_review_frames', None)
    facts['delivery'].pop('whisper_character_similarity', None)
    media_check = ROOT / 'docs/rounds/第十二轮视频边界与字幕验收.json'
    voice_check = ROOT / 'docs/demo/第十二轮语音转写回验.json'
    video_bytes = (final / '学脉XueMai-演示视频-含旁白.mp4').stat().st_size
    if media_check.exists() and json.loads(media_check.read_text('utf8')).get('source_bytes') == video_bytes:
        facts['delivery']['visual_review_frames'] = json.loads(media_check.read_text('utf8'))['frames']
    if voice_check.exists() and json.loads(voice_check.read_text('utf8')).get('source_video_bytes') == video_bytes:
        facts['delivery']['whisper_character_similarity'] = json.loads(voice_check.read_text('utf8'))['global_character_similarity']
    facts.pop('artifacts', None)
    pairs = [('学脉XueMai-技术文档.pdf', 'xuemai-technical-report.pdf'),
             ('学脉XueMai-演示视频-含旁白.mp4', 'xuemai-demo-1080p.mp4')]
    for source, target in pairs:
        shutil.copy2(final / source, ROOT / 'docs/deliverables' / target)
    facts['artifact_files'] = {'docs/deliverables/' + target: {'bytes': (final / source).stat().st_size}
                               for source, target in pairs}
    release = {'round': number, 'version': facts['version'],
               'source_commit': facts['material_baseline_commit'],
               'source_scope': '本轮开始时的基线，后续阶段记录见Git历史',
               'verification': facts['delivery'], 'real_ai': facts['real_ai']['round10'],
               'files': [{'name': source, 'bytes': (final / source).stat().st_size}
                         for source, _ in pairs]}
    (ROOT / 'docs/submission-facts.json').write_text(json.dumps(facts, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    (ROOT / 'docs/deliverables/release-manifest.json').write_text(json.dumps(release, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    result = {'pdf_pages': len(document), 'video_seconds': duration,
              'resolution': [1920, 1080], 'fps': 30, 'audio_present': True,
              'submission_files': sorted(path.name for path in final.iterdir()), 'working_sources': current['project'],
              'new_deepseek_requests': 0, 'new_review_zip': False, 'full_system_capture': False}
    (ROOT / 'docs/rounds/当前正式提交目录验收.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
