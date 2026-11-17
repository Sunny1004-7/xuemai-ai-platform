"""核对官方材料完整性与内容一致性，不调用模型、不计算文件哈希。"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote
import zipfile

import av
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_submission import EVIDENCE_NAME, HISTORY_NAME, REQUIRED_SOURCE, SOURCE_NAME


def audit(root: Path = ROOT) -> dict:
    final = root / '最终参赛提交材料'
    expected = {SOURCE_NAME, EVIDENCE_NAME, HISTORY_NAME, 'README.md',
                '学脉XueMai-技术文档.pdf', '学脉XueMai-演示视频-含旁白.mp4'}
    assert {p.name for p in final.iterdir()} == expected, '正式提交文件缺失或包含多余目录'
    assert all(p.is_file() for p in final.iterdir())
    guide = (final / 'README.md').read_text('utf8')
    assert '10分钟' in guide and '.env.example' in guide and 'requirements.txt' in guide
    assert '20.19' in guide and 'Chrome' in guide
    assert '我们' not in guide and '我' not in guide
    links = re.findall(r'\]\(([^)]+)\)', guide)
    for target in links:
        if not target.startswith(('https:', 'http:')):
            assert (final / unquote(target.split('#')[0])).is_file(), 'README存在失效本地链接'
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root).decode().strip()
    history = (final / HISTORY_NAME).read_text('utf8')
    assert head in history
    subjects = subprocess.check_output(['git', 'log', '--format=%s'], cwd=root).decode('utf8').splitlines()
    assert all(re.search('[\u4e00-\u9fff]', line) for line in subjects)
    with zipfile.ZipFile(final / SOURCE_NAME) as archive:
        names = set(archive.namelist())
        assert all('xuemai/' + name in names for name in REQUIRED_SOURCE)
        assert head in archive.read('xuemai/源码版本.txt').decode('utf8')
        archived_readme = archive.read('xuemai/README.md').decode('utf-8-sig').replace('\r\n', '\n')
        working_readme = (root / 'README.md').read_text('utf-8-sig')
        assert archived_readme == working_readme, '源码README正文与当前提交不一致'
        source_guide = archive.read('xuemai/README.md').decode('utf8')
        for target in re.findall(r'\]\(([^)]+)\)', source_guide):
            if not target.startswith(('https:', 'http:')):
                relative = unquote(target.split('#')[0]).rstrip('/')
                assert 'xuemai/' + relative in names or any(name.startswith('xuemai/' + relative + '/') for name in names), '源码README存在失效相对链接'
        current = json.loads(archive.read('xuemai/docs/demo/current.json'))['project']
        assert 'xuemai/' + current + '/scenes-source.json' in names
        assert 'xuemai/frontend/e2e/fixtures/voice-stack-queue.mp3' in names
        for public, stored in [('学脉XueMai-技术文档.pdf', 'xuemai-technical-report.pdf'),
                               ('学脉XueMai-演示视频-含旁白.mp4', 'xuemai-demo-1080p.mp4')]:
            assert archive.read('xuemai/docs/deliverables/' + stored) == (final / public).read_bytes(), '源码中的成品副本与正式文件不一致'
        source_files = sum(not name.endswith('/') for name in names)
    with zipfile.ZipFile(final / EVIDENCE_NAME) as evidence:
        assert evidence.testzip() is None
        prefix = 'AI协同开发记录/'
        transcript = evidence.read(prefix + '004-核心功能实际协作逐字转存.md').decode('utf8')
        assert len(re.findall(r'^## 链[一二三]：', transcript, re.M)) == 3
        assert all(word in transcript for word in ['Prompt', '反馈', '修复', '结果'])
        evidence.read(prefix + 'CODEX_TASK.md')
        evidence.read(prefix + '三条核心功能Prompt原文.html')
        for commit in set(re.findall(r'\b[0-9a-f]{7}\b', transcript)):
            subprocess.run(['git', 'cat-file', '-e', commit + '^{commit}'], cwd=root, check=True)
        raw = json.loads(evidence.read(prefix + 'raw-evidence/manifest.json'))
        assert '正文' in raw['evidence_status']
    with pymupdf.open(final / '学脉XueMai-技术文档.pdf') as pdf:
        assert 0 < len(pdf) <= 30 and not pdf.is_encrypted
        text = ''.join(p.get_text() for p in pdf)
        assert all(term in text for term in ['意图控制', '架构', '复现', '参考文献', 'K-TRACE', 'PATH-G', 'DIA-GUIDE', 'CLASS-LOOP', 'DIA-TEACH'])
        assert '我' not in text and '\ufffd' not in text
        cover = pdf[0].get_text()
        assert all(term in cover for term in ['参赛学生', '刘嘉程', '刘帅', '西安交通大学', '代码仓库'])
        assert '文档日期' not in cover and '系统版本' not in cover
        fonts = {font[0] for page in pdf for font in page.get_fonts(full=True)}
        assert all(bool(pdf.extract_font(xref)[3]) for xref in fonts)
        assert all(not link.get('uri', '').startswith(('file:', 'C:', 'D:')) for page in pdf for link in page.get_links())
        pdf_pages = len(pdf)
    with av.open(str(final / '学脉XueMai-演示视频-含旁白.mp4')) as movie:
        stream = movie.streams.video[0]
        seconds = movie.duration / av.time_base
        assert 300 <= seconds <= 480 and (stream.width, stream.height) == (1920, 1080)
        assert stream.codec_context.name == 'h264' and movie.streams.audio
        assert movie.streams.audio[0].codec_context.name == 'aac'
    project = root / current
    timeline = json.loads((project / 'edit-timeline.json').read_text('utf8'))
    assert abs(timeline['duration_seconds'] - seconds) < .1
    assert timeline['development_evidence_seconds'] >= 120
    assert timeline['system_interface_seconds'] > timeline['development_evidence_seconds']
    ledger = json.loads((root / 'docs/experiments/round10/token-ledger.json').read_text('utf8'))
    assert all(row['status'] != 'reserved' for row in ledger['rows'])
    assert sum(row['charged'] for row in ledger['rows']) == ledger['charged_or_reserved'] <= ledger['limit']
    return {'files': sorted(expected), 'source_commit': head, 'source_files': source_files,
            'git_commits': len(subjects), 'readme_local_links': 'passed', 'source_readme_links': 'passed',
            'source_artifact_copies': 'identical', 'prompt_feature_chains': 3,
            'prompt_provenance': '三条功能链为可见消息逐字转存；自动快照正文缺口保留说明，不视为全量原始聊天导出',
            'pdf_pages': pdf_pages, 'fonts_embedded': True, 'video_seconds': seconds,
            'resolution': [1920, 1080], 'development_seconds': timeline['development_evidence_seconds'],
            'system_seconds': timeline['system_interface_seconds'],
            'settled_api_requests': len(ledger['rows']), 'settled_tokens': ledger['charged_or_reserved'],
            'new_api_requests': 0, 'new_hash_manifest': False}


if __name__ == '__main__':
    result = audit()
    local = ROOT / '.local'
    local.mkdir(exist_ok=True)
    (local / '官方材料最终审查.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(result, ensure_ascii=False))
