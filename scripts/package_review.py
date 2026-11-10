"""生成可供逐轮审阅的完整工程ZIP，并验证收录内容与敏感信息。"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.check_secrets import SECRET_PATTERN
from scripts.review_screenshots import validate_screenshots

BEIJING = timezone(timedelta(hours=8))
EXCLUDED_DIRECTORIES = {
    '.git', '.venv', '.local', '.pytest_cache', '__pycache__', 'node_modules',
    'dist', 'data', 'logs', 'htmlcov', 'test-results', 'playwright-report', '交付审阅包',
}
EXCLUDED_SUFFIXES = {'.zip', '.7z', '.rar', '.log', '.pyc', '.pyo', '.tsbuildinfo', '.key', '.pem'}


def excluded_file(path: Path) -> bool:
    name = path.name.casefold()
    return (
        (name.startswith('.env') and name != '.env.example')
        or name in {'deepseek官方api.txt', '.git', '.coverage', '.ds_store', 'thumbs.db'}
        or 'credentials' in name
        or 'api_key' in name
        or path.suffix.casefold() in EXCLUDED_SUFFIXES
    )


def source_files(root: Path):
    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        directories[:] = sorted(
            name for name in directories
            if name not in EXCLUDED_DIRECTORIES
            and not (current_path / name).is_symlink()
            and not (current_path / name).is_junction()
        )
        for name in sorted(filenames):
            path = current_path / name
            if not path.is_symlink() and not excluded_file(path):
                yield path


def git_output(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ['git', *arguments], cwd=root, capture_output=True, encoding='utf-8', errors='replace',
    )
    if result.returncode:
        raise RuntimeError('Git记录读取失败，请检查仓库与本轮起始提交。')
    return result.stdout


def build_review_package(
    root: Path, record: Path, base_ref: str | None = None, timestamp: datetime | None = None,
    *, screenshots: Path,
) -> Path:
    root = root.resolve()
    record = (root / record).resolve()
    if not record.is_relative_to(root) or not record.is_file():
        raise ValueError('本轮修改记录必须是工程目录内的现有文件。')
    record_name = record.relative_to(root).as_posix()
    if any(part in EXCLUDED_DIRECTORIES for part in record.relative_to(root).parts) or excluded_file(record):
        raise ValueError('本轮修改记录位于打包排除范围，请放入 docs/rounds。')
    screenshot_manifest, screenshot_files = validate_screenshots(root, screenshots, record_name)
    screenshot_directory = (root / screenshots).resolve()

    generated_at = (timestamp or datetime.now(BEIJING)).astimezone(BEIJING)
    output_directory = root / '交付审阅包'
    output_directory.mkdir(exist_ok=True)
    output = output_directory / f'学脉XueMai_完整审阅包_{generated_at:%Y%m%d_%H%M%S}.zip'
    temporary = output.with_suffix('.zip.partial')
    if output.exists() or temporary.exists():
        raise FileExistsError('同一秒的审阅包已存在，请下一秒重试。')

    local_key = root / 'deepseek官方api.txt'
    key_match = None
    if local_key.is_file():
        key_match = re.search(rb'sk-[A-Za-z0-9_-]{16,}', local_key.read_bytes())
    secret = key_match.group() if key_match else None

    entries = []

    def check_content(name: str, content: bytes):
        if SECRET_PATTERN.search(content) or (secret and secret in content):
            raise ValueError(f'敏感信息检查失败，请检查文件 {name}。')

    def add_entry(archive: zipfile.ZipFile, name: str, content: bytes):
        check_content(name, content)
        archive.writestr(name, content)
        entries.append({
            'path': name, 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
        })

    head = None
    status = None
    history = None
    patch = None
    if (root / '.git').exists():
        head = git_output(root, 'rev-parse', 'HEAD').strip()
        status = git_output(root, 'status', '--short')
        history = git_output(root, 'log', '--date=iso-strict', '--format=%H %ad %s')
        if base_ref:
            # 审阅补丁必须包含原始二进制，不能依赖本机PDF转换器或外部diff程序。
            patch = git_output(root, 'diff', '--no-ext-diff', '--no-textconv', '--binary', base_ref, '--', '.', ':(exclude)交付审阅包')

    guide = (
        '# 学脉完整审阅包\n\n'
        f'生成于 {generated_at:%Y-%m-%d %H:%M:%S} 北京时间。\n\n'
        f'本轮修改记录见 [{record_name}]({record_name})。当前项目状态见 PROJECT_STATE.md，'
        '需求依据见 CODEX_TASK.md，启动与账号见 README.md。\n\n'
        '根目录“启动学脉.cmd”供Windows人工双击启动。解压后的首次启动会准备缺少的依赖，'
        '默认自动选择AI模式：后端配置Key时使用DeepSeek官方接口，无Key时使用Mock；'
        '离线审阅可运行 scripts/start.ps1 -MockAI。\n\n'
        '完整源码、文档、官方手册、现有教学和演示视频按当前目录收录。'
        '各份文档与视频保留其原有内容日期，文件摘要见“审阅清单.json”。\n\n'
        f'本轮界面覆盖 {len(screenshot_manifest["modules"])} 个模块视图，'
        f'共 {len(screenshot_manifest["files"])} 张实际PNG。'
        '先打开“界面截图/截图总览.html”浏览缩略图，再点开原图，'
        '也可按“界面截图/截图索引.md”逐模块审阅。'
        '每个模块含桌面与手机窄屏全页图，长页及长弹窗附分段图。'
        '截图使用隔离合成数据和本地Mock，详细状态见截图清单。\n\n'
        '凭据、依赖、运行数据、缓存、历史压缩包及既往审阅包已按脚本规则过滤。'
        '可从迁移和种子数据初始化演示系统。\n\n'
        f'源码Git提交为 {head or "当前目录未包含Git元数据"}。\n'
    )

    try:
        with temporary.open('xb') as handle:
            with zipfile.ZipFile(handle, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                for path in source_files(root):
                    before = path.stat()
                    content = path.read_bytes()
                    after = path.stat()
                    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                        raise RuntimeError('打包期间文件发生变化，请修改结束后重新打包。')
                    name = path.relative_to(root).as_posix()
                    add_entry(archive, name, content)
                    entries[-1]['modified_at'] = datetime.fromtimestamp(after.st_mtime, BEIJING).isoformat()
                screenshot_hashes = {entry['path']: entry['sha256'] for entry in screenshot_manifest['files']}
                for path in screenshot_files:
                    relative = path.relative_to(screenshot_directory).as_posix()
                    content = path.read_bytes()
                    if relative in screenshot_hashes and hashlib.sha256(content).hexdigest() != screenshot_hashes[relative]:
                        raise RuntimeError('截图在打包期间发生变化，请重新打包。')
                    add_entry(archive, f'界面截图/{relative}', content)
                add_entry(archive, '审阅包说明.md', guide.encode('utf-8'))
                if history is not None:
                    add_entry(archive, 'Git提交记录.txt', history.encode('utf-8'))
                if patch is not None:
                    add_entry(archive, '本轮修改.patch', patch.encode('utf-8'))
                manifest = {
                    'generated_at_beijing': generated_at.isoformat(), 'round_record': record_name,
                    'source_commit': head, 'source_worktree_status': status, 'base_ref': base_ref,
                    'screenshots': {'directory': '界面截图', 'modules': len(screenshot_manifest['modules']),
                                    'images': len(screenshot_manifest['files']),
                                    'captured_at': screenshot_manifest['captured_at'],
                                    'source_fingerprint': screenshot_manifest['source_fingerprint']},
                    'file_count': len(entries), 'files': entries,
                    'excluded_directories': sorted(EXCLUDED_DIRECTORIES),
                    'excluded_suffixes': sorted(EXCLUDED_SUFFIXES),
                }
                raw_manifest = json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8')
                check_content('审阅清单.json', raw_manifest)
                archive.writestr('审阅清单.json', raw_manifest)

        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise RuntimeError('ZIP完整性校验失败。')
            if len(archive.namelist()) != len(entries) + 1:
                raise RuntimeError('ZIP文件数量与清单不一致。')
            for entry in entries:
                content = archive.read(entry['path'])
                if hashlib.sha256(content).hexdigest() != entry['sha256']:
                    raise RuntimeError('ZIP文件摘要校验失败。')
        if output.exists():
            raise FileExistsError('目标审阅包已存在，已保留原文件。')
        temporary.rename(output)
    finally:
        temporary.unlink(missing_ok=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', required=True, type=Path, help='本轮修改记录的工程相对路径')
    parser.add_argument('--base-ref', help='本轮修改前的Git提交，用于生成本轮补丁')
    parser.add_argument('--screenshots', required=True, type=Path, help='本轮完整截图目录，位于交付审阅包内')
    args = parser.parse_args()
    output = build_review_package(ROOT, args.record, args.base_ref, screenshots=args.screenshots)
    print(f'审阅包已生成并完成完整性、SHA256及敏感信息检查\n{output}\n{output.stat().st_size:,} 字节')


if __name__ == '__main__':
    main()
