"""集中生成官方提交文件；源码来自当前已提交的Git树，不收录本机凭据或运行数据。"""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = '学脉XueMai-完整源码.zip'
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
    try:
        subprocess.run(['git', 'archive', '--format=zip', '--prefix=xuemai/',
                        '--output=' + str(temporary), head], cwd=root, check=True)
        with zipfile.ZipFile(temporary, 'a', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('xuemai/Git提交记录.txt', history.encode('utf8'))
            archive.writestr('xuemai/源码版本.txt',
                             f'代码仓库：{REPOSITORY}\n源码提交：{head}\n完整Git历史：{REPOSITORY}/commits/main/\n'.encode('utf8'))
        key = root / 'deepseek官方api.txt'
        match = re.search(rb'sk-[A-Za-z0-9_-]{16,}', key.read_bytes()) if key.is_file() else None
        count = validate_archive(temporary, match.group() if match else None)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return {'source_commit': head, 'source_files': count,
            'source_bytes': output.stat().st_size, 'git_commits': len(history.splitlines())}


def main():
    final = ROOT / '最终参赛提交材料'
    final.mkdir(exist_ok=True)
    result = build_source(ROOT, final / SOURCE_NAME)
    shutil.copy2(ROOT / 'docs/submission/README.md', final / 'README.md')
    evidence = final / 'AI协同开发记录'
    evidence.mkdir(exist_ok=True)
    shutil.copy2(ROOT / 'docs/submission/AI协同开发记录说明.md', evidence / 'README.md')
    source = ROOT / 'docs/development-process'
    for name in ['000-启动与真实指令.md', '001-业务闭环.md', '002-前端交互.md',
                 '003-AI服务.md', '004-核心功能实际协作逐字转存.md']:
        shutil.copy2(source / name, evidence / name)
    shutil.copy2(ROOT / 'CODEX_TASK.md', evidence / 'CODEX_TASK.md')
    shutil.copytree(source / 'raw-evidence', evidence / 'raw-evidence', dirs_exist_ok=True)
    history = final / 'Git演进记录'
    history.mkdir(exist_ok=True)
    (history / 'Git提交记录.txt').write_text(git('log', '--date=iso-strict', '--format=%H %ad %s'), encoding='utf8')
    (history / '代码仓库.txt').write_text(
        f'代码仓库：{REPOSITORY}\n完整Git历史：{REPOSITORY}/commits/main/\n'
        f'源码提交：{result["source_commit"]}\n提交数量：{result["git_commits"]}\n'
        '源码ZIP为当前提交快照；完整历史保留在Public仓库，可通过git clone获取。\n', encoding='utf8')
    local = ROOT / '.local'
    local.mkdir(exist_ok=True)
    (local / '正式提交材料归集结果.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
