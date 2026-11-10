import pytest


@pytest.fixture(autouse=True)
def compact_fixture(monkeypatch):
    # 原有业务用例保留精简场景；多人场景用例显式开启扩充样本。
    monkeypatch.setenv('XUEMAI_DEMO_COHORT', '0')
    monkeypatch.setenv('AI_MODE', 'mock')
