"""Test fixtures and configuration"""

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """返回测试 fixtures 目录"""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def safe_skills_dir(fixtures_dir: Path) -> Path:
    """返回安全 Skill 目录"""
    return fixtures_dir / "skills" / "safe"


@pytest.fixture
def malicious_skills_dir(fixtures_dir: Path) -> Path:
    """返回恶意 Skill 目录"""
    return fixtures_dir / "skills" / "malicious"


@pytest.fixture
def builtin_rules_dir() -> Path:
    """返回内置规则目录"""
    return Path(__file__).parent.parent / "src" / "skill_auditor" / "rules" / "builtin"
