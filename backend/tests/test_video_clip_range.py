"""防止片段末尾带入下一张画板。"""
import pytest

from scripts.media_timeline import validate_clip_range


def test_old_framework_offset_would_include_the_next_board():
    with pytest.raises(ValueError, match='安全结束时间'):
        validate_clip_range({'capture_at': 32.4826, 'valid_until': 56.283}, 24)


def test_native_clock_with_guard_preserves_exact_output_duration():
    validate_clip_range({'capture_at': 32.3, 'valid_until': 57.3}, 24)
    with pytest.raises(ValueError):
        validate_clip_range({'capture_at': 32.3, 'valid_until': 57.3}, 24.6)
