"""统一解析当前视频工程，保留历史工程的显式重建入口。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_project(round_number=None):
    current = json.loads((ROOT / 'docs/demo/current.json').read_text('utf8'))
    number = current['round'] if round_number is None else int(round_number)
    if number == current['round']:
        project = ROOT / current['project']
    else:
        history = {7: '第七轮', 8: '第八轮', 9: '第九轮', 10: '第十轮', 11: '第十一轮'}
        if number not in history:
            raise ValueError('该视频工程未配置，请检查docs/demo/current.json')
        project = ROOT / ('docs/demo/' + history[number] + '演示源')
    return current, number, project
