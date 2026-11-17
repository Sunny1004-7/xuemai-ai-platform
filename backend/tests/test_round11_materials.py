"""保护本轮图源所有权、封面元信息及README格式。"""
import json
from pathlib import Path

from scripts import build_round10_figures
from scripts.subtitle_layout import caption_center

ROOT = Path(__file__).resolve().parents[2]


def test_three_edited_figures_survive_rebuilding_other_diagrams(tmp_path, monkeypatch):
    names = ['path-search', 'class-loop', 'deployment']
    for name in names:
        (tmp_path / (name + '.tex')).write_text('独立维护的图源\n', encoding='utf8')
    monkeypatch.setattr(build_round10_figures, 'FIG', tmp_path)
    build_round10_figures.main()
    for name in names:
        assert (tmp_path / (name + '.tex')).read_text('utf8') == '独立维护的图源\n'
    assert (tmp_path / 'evidence.tex').exists()
    assert (tmp_path / 'actions.tex').exists()


def test_cover_reads_student_and_supervisor_from_shared_metadata():
    facts = json.loads((ROOT / 'docs/submission-facts.json').read_text('utf8'))
    cover = (ROOT / 'docs/technical-report/main.tex').read_text('utf8')
    generator = (ROOT / 'scripts/build_framework.py').read_text('utf8')
    assert facts['author']['supervisor'] == '刘帅'
    assert '参赛学生：' in cover and '指导教师：' in cover
    assert '参赛作者：' not in cover and '系统版本：' not in cover
    assert '\\supervisorName' in cover and "author['supervisor']" in generator


def test_readme_has_centered_figure_and_indented_plain_paragraphs():
    source = (ROOT / 'README.md').read_text('utf8')
    assert '<p align="center">' in source
    assert 'docs/figures/xuemai-framework.svg' in source
    assert '系统版本' not in source and '使用边界与赛事证据' not in source
    in_code = False
    previous_blank = True
    for line in source.splitlines():
        if line.startswith('```'):
            in_code = not in_code
        elif not in_code and line and previous_blank:
            if not line.startswith(('#', '|', '<', '-', '1.', '2.', '3.', '4.', '5.')):
                assert line.startswith('\u3000\u3000'), line
        previous_blank = not line.strip()


def test_video_follows_modules_and_keeps_framework_stationary():
    current = json.loads((ROOT / 'docs/demo/current.json').read_text('utf8'))
    project = ROOT / current['project']
    scenes = json.loads((project / 'scenes-source.json').read_text('utf8'))
    modules = [scene for scene in scenes if scene['role'] in ['student', 'teacher']]
    assert len({scene['scene_id'] for scene in scenes}) == len(scenes)
    assert [scene['role'] for scene in modules] == ['student'] * 10 + ['teacher'] * 9
    assert [scene['module'] for scene in modules[:10]] == [
        'dashboard', 'plan', 'video', 'resources', 'graph', 'practice', 'review', 'experiments', 'tutor', 'classroom',
    ]
    assert sum(scene['duration'] for scene in scenes if scene['role'] == 'development') >= 120
    board = (project / 'boards.html').read_text('utf8')
    assert 'AI协同过程复现展示' in board
    assert 'frame.style.transform=' not in board and 'scale(${zoom})' not in board


def test_subtitle_uses_actual_content_boundary():
    assert caption_center({'width': 1920, 'height': 1080, 'content_bottom': 1000}) == (960, 1040)
    assert caption_center({'width': 1920, 'height': 1080, 'content_bottom': 932}) == (960, 1006)
