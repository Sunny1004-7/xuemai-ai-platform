from datetime import datetime
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import zlib

import pytest

from scripts.package_review import BEIJING, build_review_package
from scripts.review_screenshots import SOURCE_DIRECTORIES, SOURCE_FILES, source_fingerprint, validate_screenshots


def make_file(root: Path, name: str, content: bytes = b'content'):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def make_screenshots(root: Path):
    for directory in SOURCE_DIRECTORIES:
        (root / directory).mkdir(parents=True, exist_ok=True)
    for name in SOURCE_FILES:
        if not (root / name).exists():
            make_file(root, name)
    plan = {'desktop': {'width': 1440, 'height': 1000}, 'mobile': {'width': 390, 'height': 844},
            'modules': [{'id': 'login', 'role': 'public', 'label': '登录', 'route': '/',
                         'navigation': False, 'details': ['login-error']}]}
    make_file(root, 'frontend/scripts/review-capture-plan.json', json.dumps(plan).encode())
    directory = Path('交付审阅包/界面截图_20261110_152000')
    entries = []
    for viewport, state in [('desktop', 'full'), ('mobile', 'full'), ('desktop', 'login-error')]:
        width, height = plan[viewport]['width'], plan[viewport]['height']

        def chunk(kind, data):
            return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))

        content = b'\x89PNG\r\n\x1a\n'
        content += chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0))
        content += chunk(b'IDAT', zlib.compress((b'\0' * (width + 1)) * height))
        content += chunk(b'IEND', b'')
        name = f'public/login/{viewport}_{state}.png'
        make_file(root, (directory / name).as_posix(), content)
        entries.append({'path': name, 'role': 'public', 'module': 'login', 'viewport': viewport,
                        'state': state, 'width': width, 'height': height, 'bytes': len(content),
                        'sha256': hashlib.sha256(content).hexdigest()})
    manifest = {'version': 1, 'status': 'complete', 'round_record': 'docs/rounds/current.md',
                'captured_at': '2026-11-10T07:20:00Z', 'source_fingerprint': source_fingerprint(root),
                'ai_mode': 'mock', 'real_ai_requests': 0, 'viewports': {v: plan[v] for v in ('desktop', 'mobile')},
                'modules': plan['modules'], 'files': entries, 'page_errors': []}
    make_file(root, (directory / '截图清单.json').as_posix(), json.dumps(manifest).encode())
    make_file(root, (directory / '截图索引.md').as_posix())
    make_file(root, (directory / '截图总览.html').as_posix())
    return directory


def test_complete_review_archive_keeps_current_materials_and_filters_local_artifacts(tmp_path):
    keep = [
        'README.md', '启动学脉.cmd', 'backend/app/main.py', 'frontend/src/main.tsx',
        'docs/rounds/current.md', 'docs/report.pdf', '最终参赛提交材料/demo.mp4',
        'backend/media/lesson.mp4', '大赛官方资料/官方参赛手册.pdf', '.env.example',
        'untracked-current-source.py',
    ]
    omit = [
        '.env', '.env.production', 'deepseek官方api.txt', '.git/config',
        'frontend/node_modules/private.txt', 'node_modules/private.txt', '.venv/private.txt',
        '.local/private.txt', 'data/current.db', 'frontend/dist/bundle.js',
        '最终参赛提交材料/old-source.zip', '交付审阅包/previous.zip',
    ]
    for name in keep + omit:
        make_file(tmp_path, name)
    # This fixture is a directory tree, so Git metadata is intentionally absent.
    (tmp_path / '.git/config').unlink()
    (tmp_path / '.git').rmdir()
    at = datetime(2026, 11, 10, 15, 20, 30, tzinfo=BEIJING)
    screenshots = make_screenshots(tmp_path)
    output = build_review_package(tmp_path, Path('docs/rounds/current.md'), timestamp=at, screenshots=screenshots)
    assert output.name == '学脉XueMai_完整审阅包_20261110_152030.zip'
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        names = set(archive.namelist())
        assert set(keep) <= names
        assert not set(omit) & names
        manifest = json.loads(archive.read('审阅清单.json'))
        assert manifest['generated_at_beijing'].endswith('+08:00')
        assert manifest['round_record'] == 'docs/rounds/current.md'
        assert manifest['file_count'] + 1 == len(names)
        assert manifest['screenshots']['images'] == 3
        assert '界面截图/public/login/mobile_full.png' in names
        assert '界面截图/截图总览.html' in names
        for entry in manifest['files']:
            assert hashlib.sha256(archive.read(entry['path'])).hexdigest() == entry['sha256']


def test_secret_in_source_rejects_archive_without_disclosing_value(tmp_path):
    make_file(tmp_path, 'docs/rounds/current.md')
    fixture_secret = b'sk-' + b'x' * 32
    make_file(tmp_path, 'backend/app/leak.py', fixture_secret)
    screenshots = make_screenshots(tmp_path)
    with pytest.raises(ValueError) as error:
        build_review_package(tmp_path, Path('docs/rounds/current.md'), screenshots=screenshots)
    assert fixture_secret.decode() not in str(error.value)
    assert not list((tmp_path / '交付审阅包').glob('*.zip*'))


def test_second_precision_collision_preserves_existing_archive(tmp_path):
    make_file(tmp_path, 'docs/rounds/current.md')
    at = datetime(2026, 11, 10, 15, 20, 30, tzinfo=BEIJING)
    screenshots = make_screenshots(tmp_path)
    output = build_review_package(tmp_path, Path('docs/rounds/current.md'), timestamp=at, screenshots=screenshots)
    original = output.read_bytes()
    with pytest.raises(FileExistsError):
        build_review_package(tmp_path, Path('docs/rounds/current.md'), timestamp=at, screenshots=screenshots)
    assert output.read_bytes() == original


def test_round_record_must_be_included_and_within_project(tmp_path):
    record = make_file(tmp_path, '.local/current.md')
    with pytest.raises(ValueError):
        build_review_package(tmp_path, record, screenshots=Path('交付审阅包/missing'))
    with pytest.raises(ValueError):
        build_review_package(tmp_path, Path('../outside.md'), screenshots=Path('交付审阅包/missing'))


@pytest.mark.parametrize('case', ['missing-file', 'changed-file', 'missing-state', 'missing-module',
                                  'wrong-round', 'stale-source', 'failed', 'real-ai', 'escape', 'missing-index'])
def test_incomplete_or_stale_screenshots_are_rejected(tmp_path, case):
    make_file(tmp_path, 'docs/rounds/current.md')
    directory = make_screenshots(tmp_path)
    manifest_path = tmp_path / directory / '截图清单.json'
    manifest = json.loads(manifest_path.read_text())
    image = tmp_path / directory / manifest['files'][0]['path']
    if case == 'missing-file':
        image.unlink()
    elif case == 'changed-file':
        image.write_bytes(image.read_bytes() + b'changed')
    elif case == 'missing-state':
        manifest['files'].pop()
    elif case == 'missing-module':
        manifest['modules'] = []
    elif case == 'wrong-round':
        manifest['round_record'] = 'docs/rounds/previous.md'
    elif case == 'stale-source':
        make_file(tmp_path, 'frontend/src/main.tsx', b'changed UI')
    elif case == 'failed':
        manifest['status'] = 'failed'
    elif case == 'real-ai':
        manifest['real_ai_requests'] = 1
    elif case == 'escape':
        manifest['files'][0]['path'] = '../../../outside.png'
    elif case == 'missing-index':
        (tmp_path / directory / '截图索引.md').unlink()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        validate_screenshots(tmp_path, directory, 'docs/rounds/current.md')
