"""集中生成官方提交文件；源码来自当前已提交的Git树，不收录本机凭据或运行数据。"""
from __future__ import annotations

import json
import html
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = '学脉XueMai-完整源码.zip'
EVIDENCE_NAME = '学脉XueMai-AI协同开发记录.zip'
HISTORY_NAME = 'Git演进记录.txt'
REPOSITORY = 'https://github.com/Sunny1004-7/xuemai-ai-platform'
REQUIRED_SOURCE = {
    'README.md', '.env.example', '启动学脉.cmd', 'backend/requirements.txt',
    'backend/app/main.py', 'backend/migrations/001_initial.sql',
    'backend/media/python-teaching-metadata.json', 'backend/media/teaching-metadata.json',
    'frontend/package.json', 'frontend/package-lock.json', 'frontend/src/main.tsx',
    'scripts/setup.ps1', 'scripts/start.ps1', 'scripts/stop.ps1',
    'docs/development-process/004-核心功能实际协作逐字转存.md',
}
CLIPS = {'sorting-demo', 'stack-demo', 'binary-search-demo',
         'python-loop', 'python-list', 'python-function'}
REQUIRED_SOURCE.update(f'backend/media/{name}.mp4' for name in CLIPS)
FORBIDDEN_PARTS = {'.git', '.venv', '.local', 'node_modules', '__pycache__',
                   '最终参赛提交材料', '交付审阅包'}
SECRET_PATTERN = re.compile(rb'sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9_]{24,}|github_pat_[A-Za-z0-9_]{24,}')
MEDIA_SUFFIXES = {'.mp4', '.webm', '.wav', '.mp3', '.flac', '.png', '.jpg', '.jpeg'}


def historical_media(name: str, current_project: str) -> bool:
    """当前材料源完整保留，旧轮媒体通过Public仓库历史提供。"""
    relative = PurePosixPath(name).relative_to('xuemai')
    return (relative.as_posix().startswith('docs/demo/')
            and not relative.as_posix().startswith(current_project.rstrip('/') + '/')
            and relative.suffix.lower() in MEDIA_SUFFIXES)


def git(*args: str, root: Path = ROOT) -> str:
    return subprocess.check_output(['git', *args], cwd=root).decode('utf8')


def validate_archive(path: Path, local_secret: bytes | None = None) -> int:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('源码包存在重复文件')
        missing = {f'xuemai/{name}' for name in REQUIRED_SOURCE} - set(names)
        if missing:
            raise ValueError('源码包缺少必要文件：' + ', '.join(sorted(missing)))
        for info in archive.infolist():
            name = PurePosixPath(info.filename)
            if name.is_absolute() or '..' in name.parts or name.parts[0] != 'xuemai':
                raise ValueError('源码包存在不安全路径')
            if FORBIDDEN_PARTS.intersection(name.parts):
                raise ValueError('源码包包含本机或历史交付目录')
            if ((name.name.startswith('.env') and name.name != '.env.example')
                    or name.suffix in {'.key', '.pem'} or 'deepseek官方api' in name.name):
                raise ValueError('源码包包含凭据文件')
            # 读取时同时验证ZIP的CRC，不另行计算文件哈希。
            content = archive.read(info)
            if SECRET_PATTERN.search(content) or (local_secret and local_secret in content):
                raise ValueError('源码包敏感信息检查失败，仅定位文件：' + info.filename)
        return sum(not entry.is_dir() for entry in archive.infolist())


def build_source(root: Path, output: Path) -> dict:
    if git('status', '--porcelain', '--untracked-files=no', root=root).strip():
        raise ValueError('请先提交当前修改，再生成与Git提交一致的源码包')
    head = git('rev-parse', 'HEAD', root=root).strip()
    history = git('log', '--date=iso-strict', '--format=%H %ad %s', root=root)
    temporary = output.with_suffix('.zip.partial')
    complete = output.with_suffix('.git.partial')
    current_file = root / 'docs/demo/current.json'
    current_project = json.loads(current_file.read_text('utf8'))['project'] if current_file.exists() else 'docs/demo/当前演示源'
    skipped = 0
    try:
        subprocess.run(['git', 'archive', '--format=zip', '--prefix=xuemai/',
                        '--output=' + str(complete), head], cwd=root, check=True)
        with zipfile.ZipFile(complete) as source, zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for entry in source.infolist():
                if historical_media(entry.filename, current_project):
                    skipped += 1
                    continue
                archive.writestr(entry, source.read(entry))
        with zipfile.ZipFile(temporary, 'a', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('xuemai/Git提交记录.txt', history.encode('utf8'))
            archive.writestr('xuemai/源码版本.txt',
                             f'代码仓库：{REPOSITORY}\n源码提交：{head}\n完整Git历史：{REPOSITORY}/commits/main/\n'
                             f'当前视频制作源：{current_project}\n旧轮配音、录屏与抽帧图片保留在Public仓库历史，源码ZIP仅收录当前制作媒体。\n'.encode('utf8'))
        key = root / 'deepseek官方api.txt'
        match = re.search(rb'sk-[A-Za-z0-9_-]{16,}', key.read_bytes()) if key.is_file() else None
        count = validate_archive(temporary, match.group() if match else None)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
        complete.unlink(missing_ok=True)
    return {'source_commit': head, 'source_files': count,
            'source_bytes': output.stat().st_size, 'git_commits': len(history.splitlines()),
            'historical_media_excluded': skipped}


def main():
    final = ROOT / '最终参赛提交材料'
    final.mkdir(exist_ok=True)
    result = build_source(ROOT, final / SOURCE_NAME)
    shutil.copy2(ROOT / 'docs/submission/README.md', final / 'README.md')
    staging = ROOT / '.local/submission-staging'
    evidence = staging / 'AI协同开发记录'
    evidence.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'docs/submission/AI协同开发记录说明.md', evidence / 'README.md')
    source = ROOT / 'docs/development-process'
    for name in ['000-启动与真实指令.md', '001-业务闭环.md', '002-前端交互.md',
                 '003-AI服务.md', '004-核心功能实际协作逐字转存.md']:
        shutil.copy2(source / name, evidence / name)
    shutil.copy2(ROOT / 'CODEX_TASK.md', evidence / 'CODEX_TASK.md')
    shutil.copytree(source / 'raw-evidence', evidence / 'raw-evidence', dirs_exist_ok=True)
    transcript = (evidence / '004-核心功能实际协作逐字转存.md').read_text('utf8')
    viewer = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>学脉：三条核心功能Prompt原文</title>'
              '<style>body{margin:0;background:#f6f5f0;color:#243d36;font:18px/1.85 "Microsoft YaHei",sans-serif}'
              'main{max-width:1000px;margin:40px auto;padding:32px;background:white}pre{white-space:pre-wrap;'
              'overflow-wrap:anywhere;font:inherit}a{color:#2e6a67}</style><main>'
              '<p><a href="raw-evidence/index.html">公开快照检索</a> · <a href="004-核心功能实际协作逐字转存.md">Markdown原文</a></p>'
              '<pre>' + html.escape(transcript) + '</pre></main></html>')
    (evidence / '三条核心功能Prompt原文.html').write_text(viewer, encoding='utf8')
    with zipfile.ZipFile(final / EVIDENCE_NAME, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(evidence.rglob('*')):
            if file.is_file():
                archive.write(file, 'AI协同开发记录/' + file.relative_to(evidence).as_posix())
    (final / HISTORY_NAME).write_text(
        f'代码仓库：{REPOSITORY}\n完整Git历史：{REPOSITORY}/commits/main/\n'
        f'源码提交：{result["source_commit"]}\n提交数量：{result["git_commits"]}\n'
        '源码ZIP为当前提交快照；完整历史保留在Public仓库，可通过git clone获取。\n\n'
        + git('log', '--date=iso-strict', '--format=%H %ad %s'), encoding='utf8')
    # 旧版可浏览目录保留在工程暂存区，正式目录提供可直接上传的ZIP和TXT。
    for name in ['AI协同开发记录', 'Git演进记录']:
        previous = final / name
        destination = staging / ('此前正式目录-' + name)
        if previous.is_dir():
            if previous.resolve().parent != final.resolve() or destination.exists():
                raise ValueError('旧目录转存位置不符合预期，请保留文件并检查')
            previous.rename(destination)
    local = ROOT / '.local'
    local.mkdir(exist_ok=True)
    (local / '正式提交材料归集结果.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
