"""从模块化讲稿建立当前时间轴，高亮时刻取自同次配音词语边界。"""
import html
import json
from pathlib import Path

from demo_project import load_project

ROOT = Path(__file__).resolve().parents[1]


def main():
    current, number, project = load_project()
    if number != 11:
        raise ValueError('请先将当前视频工程指定为第十一轮')
    scenes = json.loads((project / 'scenes-source.json').read_text('utf8'))
    ids = [scene['scene_id'] for scene in scenes]
    if len(set(ids)) != len(ids):
        raise ValueError('scene_id重复')
    at = 0
    for scene in scenes:
        scene['start'] = round(at, 3)
        at += scene['duration']
    if not 300 <= at <= 480:
        raise ValueError('计划片长超出赛事要求')
    (project / 'scenes.json').write_text(json.dumps(scenes, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    (ROOT / 'scripts/demo-scenes.json').write_text(json.dumps(scenes, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    facts = json.loads((ROOT / 'docs/submission-facts.json').read_text('utf8'))
    (project / 'product.json').write_text(json.dumps(facts, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    rows = ['# 模块、镜头与旁白对应', '', '| 场景 | 身份与模块 | 路由 | 时间（秒） | 实际操作 | 结果 | 讲解 |', '|---|---|---|---|---|---|---|']
    for scene in scenes:
        rows.append(f'| {scene["scene_id"]} | {scene["role"]}／{scene["name"]} | {scene["route"] or "画板与历史记录"} | {scene["start"]}—{scene["start"]+scene["duration"]} | {scene.get("operation", "连续展示")} | {scene.get("expected_result", "对应讲述内容")} | {scene["text"]} |')
    (project / '模块与镜头.md').write_text('\n'.join(rows) + '\n', encoding='utf8', newline='\n')
    metadata = project / 'audio/framework-01.jsonl'
    segments_file = project / 'audio/segments.json'
    if metadata.exists() and segments_file.exists():
        segment = next(s for s in json.loads(segments_file.read_text('utf8')) if s['scene'] == '总体方法框架')
        text = segment['text']
        cursor = 0
        boundaries = []
        for line in metadata.read_text('utf8').splitlines():
            item = json.loads(line)
            if item.get('type') != 'WordBoundary':
                continue
            word = html.unescape(item['text'])
            position = text.index(word, cursor)
            boundaries.append((position, position + len(word), item['offset'] / 1e7))
            cursor = position + len(word)
        phrases = [('shared-evidence', '课程资料'), ('student-methods', '学生侧'),
                   ('teacher-methods', '教师侧'), ('services', '共享工具'), ('feedback', '新的作答')]
        phases = [{'name': None, 'at': 0, 'spoken_phrase': '先展示全貌'}]
        for name, phrase in phrases:
            position = text.index(phrase)
            offset = next(offset for begin, end, offset in boundaries if begin <= position < end)
            phases.append({'name': name, 'at': round(max(4.3, .6 + offset / segment['tempo']), 3), 'spoken_phrase': phrase})
        (project / 'framework-phases.json').write_text(json.dumps(phases, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print('已建立', len(scenes), '个稳定场景，计划', at, '秒')


if __name__ == '__main__':
    main()
