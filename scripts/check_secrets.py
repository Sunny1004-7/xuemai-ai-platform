"""扫描已跟踪文件/暂存区，不输出秘密内容，可在每次提交前和 CI 运行。"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    staged = '--staged' in sys.argv
    args = ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM', '-z'] if staged else ['git', 'ls-files', '-z']
    names = subprocess.check_output(args, cwd=ROOT).decode('utf-8').split('\0')
    # 读取本地密钥只用于等值扫描，绝不打印或写入扫描报告。
    secret_file = ROOT / 'deepseek官方api.txt'
    local = secret_file.read_text(encoding='utf-8-sig').strip() if secret_file.exists() else ''
    secret = re.search(r'sk-[A-Za-z0-9_-]{16,}', local)
    failures = []
    for name in filter(None, names):
        if name.startswith('.env') and name != '.env.example' or name.endswith(('.pem', '.key')) or 'deepseek官方api' in name:
            failures.append(name)
            continue
        if staged:
            content = subprocess.check_output(['git', 'show', ':' + name], cwd=ROOT)
        else:
            path = ROOT / name
            if not path.is_file():
                continue
            content = path.read_bytes()
        if re.search(rb'sk-[A-Za-z0-9_-]{24,}', content) or (secret and secret.group().encode() in content):
            failures.append(name)
    if failures:
        print('敏感信息检查失败（仅列文件名）：', ', '.join(failures))
        return 1
    print(f'敏感信息检查通过：{len(list(filter(None, names)))} 个文件；未输出任何密钥。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
