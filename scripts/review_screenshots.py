"""校验逐轮截图覆盖、源码版本和PNG摘要，供审阅打包复用。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct

SOURCE_DIRECTORIES = ('frontend/src', 'frontend/public', 'backend/app', 'backend/migrations')
SOURCE_FILES = (
    'frontend/index.html', 'frontend/package.json', 'frontend/package-lock.json',
    'frontend/vite.config.ts', 'frontend/scripts/review-capture-plan.json',
)


def source_fingerprint(root: Path) -> str:
    names = list(SOURCE_FILES)
    for directory in SOURCE_DIRECTORIES:
        names.extend(
            path.relative_to(root).as_posix() for path in (root / directory).rglob('*')
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc'
        )
    digest = hashlib.sha256()
    for name in sorted(names):
        digest.update(name.encode('utf-8') + b'\0')
        digest.update((root / name).read_bytes() + b'\0')
    return digest.hexdigest()


def validate_screenshots(root: Path, directory: Path, record_name: str) -> tuple[dict, list[Path]]:
    root = root.resolve()
    directory = (root / directory).resolve()
    if not directory.is_relative_to(root / '交付审阅包') or not directory.is_dir():
        raise ValueError('截图目录必须位于本工程的交付审阅包目录内。')
    manifest_path = directory / '截图清单.json'
    if not manifest_path.is_file():
        raise ValueError('缺少完整截图清单，请先运行全模块截图脚本。')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    plan = json.loads((root / 'frontend/scripts/review-capture-plan.json').read_text(encoding='utf-8'))
    if manifest.get('version') != 1 or manifest.get('status') != 'complete' or manifest.get('page_errors') != []:
        raise ValueError('截图任务未完整成功，或存在浏览器运行错误。')
    if manifest.get('round_record') != record_name:
        raise ValueError('截图不属于本轮记录，请重新截图。')
    if manifest.get('source_fingerprint') != source_fingerprint(root):
        raise ValueError('截图与当前界面源码不一致，请重新截图。')
    if manifest.get('ai_mode') != 'mock' or manifest.get('real_ai_requests') != 0:
        raise ValueError('常规截图必须使用本地Mock且真实API请求为0。')
    viewports = {k:v for k,v in plan.items() if k not in ('modules','courses')}
    if manifest.get('modules') != plan['modules'] or manifest.get('viewports') != viewports:
        raise ValueError('截图覆盖计划与当前模块或视口不一致。')

    paths = []
    seen = set()
    coverage = set()
    for entry in manifest.get('files', []):
        name = entry['path']
        path = directory / name
        resolved = path.resolve()
        if name in seen or not resolved.is_relative_to(directory) or path.is_symlink() or path.suffix != '.png':
            raise ValueError('截图路径重复、越界或格式不合法。')
        if not path.is_file():
            raise ValueError(f'截图缺失 {name}。')
        content = path.read_bytes()
        if len(content) < 33 or content[:8] != b'\x89PNG\r\n\x1a\n' or content[12:16] != b'IHDR':
            raise ValueError(f'截图PNG头无效 {name}。')
        width, height = struct.unpack('>II', content[16:24])
        if (len(content) != entry['bytes'] or hashlib.sha256(content).hexdigest() != entry['sha256']
                or (width, height) != (entry['width'], entry['height'])):
            raise ValueError(f'截图尺寸或摘要不匹配 {name}。')
        viewport = entry['viewport']
        if viewport not in viewports or width != plan[viewport]['width'] or height <= 0:
            raise ValueError(f'截图视口尺寸不匹配 {name}。')
        coverage.add((entry['role'], entry['module'], entry.get('course'), viewport, entry['state']))
        if viewport!='mobile' and entry.get('course') and entry['state']=='full':
            layout=entry.get('layout',{})
            if height!=viewports[viewport]['height'] or layout.get('height',height)>height+2 or layout.get('width',width)>width+2:
                raise ValueError(f'桌面首屏尺寸或页面溢出 {name}。')
        seen.add(name)
        paths.append(path)

    for module in plan['modules']:
        required = [(viewport, 'full') for viewport in viewports]
        required.extend(('desktop', state) for state in module['details'])
        for course in ([None] if module['role']=='public' else plan.get('courses',[None])):
            for viewport, state in required:
                if (module['role'], module['id'], course, viewport, state) not in coverage:
                    raise ValueError(f'截图覆盖不足 {module["role"]}/{module["id"]}/{course}/{viewport}/{state}。')
    for name in ('截图清单.json', '截图索引.md', '截图总览.html'):
        path = directory / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f'截图审阅入口缺失 {name}。')
        paths.append(path)
    return manifest, paths
