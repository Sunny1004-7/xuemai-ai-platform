"""校验正式材料副本并建立方法、验证、媒体的统一事实索引。"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.review_screenshots import validate_screenshots


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    record = 'docs/rounds/2026-11-12-第七轮技术论证与连续教学演示.md'
    screenshots = '交付审阅包/界面截图_20261112_145705'
    manifest, files = validate_screenshots(ROOT, Path(screenshots), record)
    pairs = [('最终参赛提交材料/学脉XueMai-技术文档.pdf', 'docs/deliverables/xuemai-technical-report.pdf'),
             ('最终参赛提交材料/学脉XueMai-演示视频-含旁白.mp4', 'docs/deliverables/xuemai-demo-1080p.mp4')]
    artifacts = []
    for formal, tracked in pairs:
        first = digest(ROOT / formal)
        if first != digest(ROOT / tracked):
            raise RuntimeError('正式材料与仓库副本摘要不同')
        artifacts.append({'formal': formal, 'tracked': tracked, 'sha256': first, 'bytes': (ROOT / formal).stat().st_size})
    audit = json.loads((ROOT / 'docs/demo/第七轮语音转写回验.json').read_text('utf8'))
    if audit['source_video_sha256'] != artifacts[1]['sha256']:
        raise RuntimeError('语音回验对应的成片版本不同')
    methods = {
        'K-TRACE': ['backend/app/evidence.py', 'update_state / apply_evidence'],
        'PATH-G': ['backend/app/path_planner.py', 'plan_path / order_recommendations'],
        'CLASS-LOOP': ['backend/app/learning_insights.py', 'dynamic_groups'],
        'DIA-GUIDE': ['backend/app/teaching_agents.py', 'begin_collaboration / finalize_collaboration / record_feedback'],
        'DIA-TEACH': ['backend/app/teacher_assistant.py', 'prepare_teacher / validate_draft / save'],
    }
    result = {'version': '0.6.0', 'round_base': '24c236201ca01a38e93b51494ab9a863dbcb727e',
              'product_source_commit': '85d731e', 'experiment_source_commit': 'd78e8cf',
              'repository': 'https://github.com/Sunny1004-7/xuemai-ai-platform',
              'methods': methods, 'artifacts': artifacts,
              'screenshots': {'count': len(manifest['files']), 'directory': screenshots, 'source_fingerprint': manifest['source_fingerprint'], 'zoom': 1},
              'validation': {'backend_passed': 124, 'browser_passed': 31, 'delivery_subset_passed': 14,
                             'test_scope': 'backend/tests，显式排除独立test_security.py；14项交付工具属于124项内的复核'},
              'evidence': ['docs/rounds/第七轮方法实验.json', 'docs/rounds/第七轮真实API用量.json',
                           'docs/rounds/第七轮官方AI教学记录.json', 'docs/rounds/第七轮教学闭环实际结果.json',
                           'docs/development-process/008-第七轮三条开发证据链.json', 'docs/demo/第七轮演示源/edit-timeline.json',
                           'docs/demo/第七轮语音转写回验.json', 'docs/rounds/第七轮视频独立重建核验.json'],
              'synthetic_course_data': True, 'real_api_calls': 2, 'real_api_limit': 6,
              'input_tokens': 3650, 'output_tokens': 637, 'automatic_retries': 0}
    for relative in result['evidence']:
        if not (ROOT / relative).is_file():
            raise RuntimeError('缺少索引中的实际证据')
    (ROOT / 'docs/rounds/第七轮事实与证据索引.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'screenshots': len(manifest['files']), 'copies_equal': True, 'asr_matches_final_video': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
