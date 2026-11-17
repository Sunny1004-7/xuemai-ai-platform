"""官方源码快照必须可复现、与提交一致，并排除本机秘密。"""
import subprocess
import zipfile

import pytest

from scripts.prepare_submission import REQUIRED_SOURCE, build_source, validate_archive


def make_repository(root):
    subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
    subprocess.run(['git', 'config', 'user.name', '测试'], cwd=root, check=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.invalid'], cwd=root, check=True)
    for name in REQUIRED_SOURCE:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('测试源码\n', encoding='utf8')
    (root / '.gitignore').write_text('deepseek官方api.txt\n', encoding='utf8')
    demo = root / 'docs/demo'
    demo.mkdir(parents=True, exist_ok=True)
    (demo / 'current.json').write_text('{"project":"docs/demo/当前演示源"}', encoding='utf8')
    for name in ['当前演示源/media/current.mp4', '历史演示源/media/old.mp4',
                 '历史演示源/audio/old.wav', '历史演示源/scenes.json']:
        file = demo / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text('测试素材', encoding='utf8')
    subprocess.run(['git', 'add', '.'], cwd=root, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-qm', '建立可复现的测试工程'], cwd=root, check=True)


def test_source_uses_committed_tree_including_media_and_history(tmp_path):
    make_repository(tmp_path)
    (tmp_path / 'deepseek官方api.txt').write_text('private-value', encoding='utf8')
    output = tmp_path / '最终参赛提交材料/源码.zip'
    output.parent.mkdir()
    (output.parent / '旧文件.txt').write_text('不收录', encoding='utf8')
    result = build_source(tmp_path, output)
    assert result['git_commits'] == 1
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        assert 'xuemai/backend/media/python-loop.mp4' in names
        assert 'xuemai/.env.example' in names
        assert 'xuemai/docs/demo/当前演示源/media/current.mp4' in names
        assert 'xuemai/docs/demo/历史演示源/media/old.mp4' not in names
        assert 'xuemai/docs/demo/历史演示源/audio/old.wav' not in names
        assert 'xuemai/docs/demo/历史演示源/scenes.json' in names
        assert result['historical_media_excluded'] == 2
        assert not any('deepseek官方api' in name or '最终参赛提交材料' in name for name in names)
        assert result['source_commit'] in archive.read('xuemai/源码版本.txt').decode()
        assert '建立可复现的测试工程' in archive.read('xuemai/Git提交记录.txt').decode()


def test_source_refuses_uncommitted_edits(tmp_path):
    make_repository(tmp_path)
    (tmp_path / 'README.md').write_text('尚未提交', encoding='utf8')
    with pytest.raises(ValueError, match='先提交'):
        build_source(tmp_path, tmp_path / '源码.zip')


@pytest.mark.parametrize('unsafe', ['xuemai/.env', 'xuemai/../secret.txt', 'xuemai/node_modules/a.js'])
def test_source_rejects_private_or_unsafe_entries(tmp_path, unsafe):
    output = tmp_path / '源码.zip'
    with zipfile.ZipFile(output, 'w') as archive:
        for name in REQUIRED_SOURCE:
            archive.writestr('xuemai/' + name, b'code')
        archive.writestr(unsafe, b'private')
    with pytest.raises(ValueError):
        validate_archive(output)


def test_source_rejects_secret_content(tmp_path):
    output = tmp_path / '源码.zip'
    with zipfile.ZipFile(output, 'w') as archive:
        for name in REQUIRED_SOURCE:
            archive.writestr('xuemai/' + name, b'code')
        archive.writestr('xuemai/accidental.txt', b'local-secret-value')
    with pytest.raises(ValueError, match='敏感信息'):
        validate_archive(output, b'local-secret-value')
