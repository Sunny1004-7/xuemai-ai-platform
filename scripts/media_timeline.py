"""检查剪辑区间与相邻画面的保护时间。"""
import math


def validate_clip_range(recording, duration, minimum_guard=.5):
    start = recording['capture_at']
    end = recording['valid_until']
    values = (start, end, duration, minimum_guard)
    if not all(math.isfinite(value) for value in values):
        raise ValueError('剪辑时间须为有限数值')
    if start < 0 or duration <= 0 or minimum_guard < 0:
        raise ValueError('剪辑开始时间、片长或保护时间无效')
    if start + duration + minimum_guard > end + .001:
        raise ValueError('剪辑区间超出当前画面的安全结束时间')
