"""精修生成链的具体回归，全部离线执行。"""
import hashlib
import json
from pathlib import Path

import pytest

from scripts.subtitle_layout import semantic_lines


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('text', [
    '我是西安交通大学软件工程专业的刘嘉程。课程学习、个性化辅导与教学协作相互连接。',
    'K-TRACE更新知识状态，PATH-G安排活动。DIA-GUIDE检验理解。',
    '教师确认30分钟方案，再查看任务结果；学生继续学习。',
])
def test_semantic_subtitles_keep_terms_and_all_words(text):
    measure = lambda line: sum(32 if ord(character) > 127 else 18 for character in line)
    lines = semantic_lines(text, measure, max_width=760)
    assert ''.join(lines) == text
    assert all('\n' not in line and measure(line) <= 760 for line in lines)
    for term in ['西安交通大学', '刘嘉程', 'K-TRACE', 'PATH-G', 'DIA-GUIDE', '30分钟']:
        if term in text:
            assert any(term in line for line in lines)


def test_overwide_semantic_clause_requires_script_edit():
    with pytest.raises(ValueError, match='语义片段'):
        semantic_lines('一段没有自然停顿而且超宽的讲稿', len, max_width=5)


def test_framework_groups_come_from_current_tikz_anchors():
    regions = json.loads((ROOT/'docs/figures/xuemai-framework-regions.json').read_text('utf8'))
    assert hashlib.sha256((ROOT/regions['source']).read_text('utf8').encode('utf8')).hexdigest() == regions['source_sha256']
    assert regions['groups']['teacher-methods']['members'] == ['c', 't']
    assert regions['groups']['student-methods']['members'] == ['k', 'p', 'g']
    assert len(regions['groups']) == 7
    for group in regions['groups'].values():
        for name in group['members']:
            node = regions['nodes'][name]
            assert 0 <= group['x'] <= node['x']
            assert 0 <= group['y'] <= node['y']
            assert node['x'] + node['width'] <= group['x'] + group['width'] + .001
            assert node['y'] + node['height'] <= group['y'] + group['height'] + .001
        assert group['x'] + group['width'] < regions['width']
        assert group['y'] + group['height'] < regions['height']
