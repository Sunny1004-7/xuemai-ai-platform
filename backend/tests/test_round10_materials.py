"""新材料入口的回归，防止旧结果、局部截图或付费调用重新进入构建。"""
import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def test_report_builder_reads_current_experiments_and_full_images():
    source=(ROOT/'scripts/build_technical_report.py').read_text('utf8')
    assert 'report_round7_evidence.py' not in source
    assert 'build_round10_report_data.py' in source
    assert 'practice-detail' not in source and 'video-detail' not in source
    assert not any(isinstance(node,ast.Attribute) and node.attr=='crop' for node in ast.walk(ast.parse(source)))


def test_report_only_uses_two_heading_levels_and_complete_screens():
    source=(ROOT/'docs/technical-report/main.tex').read_text('utf8')
    assert '\\subsubsection' not in source
    assert '系统版本：' not in source
    assert 'practice-detail' not in source and 'video-detail' not in source
    assert '\\clearpage\\section{应用场景与总体方案}' in source


def test_material_aggregation_does_not_call_paid_service():
    source=(ROOT/'scripts/build_round10_report_data.py').read_text('utf8')
    assert 'AIService' not in source and 'httpx' not in source
    assert "read('end-to-end.json')" in source
    assert 'source_commit' in source
