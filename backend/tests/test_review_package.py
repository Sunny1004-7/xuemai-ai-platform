from datetime import datetime
import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from scripts.package_review import BEIJING, build_review_package


def make_file(root: Path, name: str, content: bytes = b'content'):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


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
    output = build_review_package(tmp_path, Path('docs/rounds/current.md'), timestamp=at)
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
        for entry in manifest['files']:
            assert hashlib.sha256(archive.read(entry['path'])).hexdigest() == entry['sha256']


def test_secret_in_source_rejects_archive_without_disclosing_value(tmp_path):
    make_file(tmp_path, 'docs/rounds/current.md')
    fixture_secret = b'sk-' + b'x' * 32
    make_file(tmp_path, 'backend/app/leak.py', fixture_secret)
    with pytest.raises(ValueError) as error:
        build_review_package(tmp_path, Path('docs/rounds/current.md'))
    assert fixture_secret.decode() not in str(error.value)
    assert not list((tmp_path / '交付审阅包').iterdir())


def test_second_precision_collision_preserves_existing_archive(tmp_path):
    make_file(tmp_path, 'docs/rounds/current.md')
    at = datetime(2026, 11, 10, 15, 20, 30, tzinfo=BEIJING)
    output = build_review_package(tmp_path, Path('docs/rounds/current.md'), timestamp=at)
    original = output.read_bytes()
    with pytest.raises(FileExistsError):
        build_review_package(tmp_path, Path('docs/rounds/current.md'), timestamp=at)
    assert output.read_bytes() == original


def test_round_record_must_be_included_and_within_project(tmp_path):
    record = make_file(tmp_path, '.local/current.md')
    with pytest.raises(ValueError):
        build_review_package(tmp_path, record)
    with pytest.raises(ValueError):
        build_review_package(tmp_path, Path('../outside.md'))
