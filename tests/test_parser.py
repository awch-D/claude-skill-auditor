"""Tests for Skill parser"""

from pathlib import Path

import pytest

from skill_auditor.core.parser import SkillParser
from skill_auditor.core.skill import SkillSource


class TestSkillParser:
    """Skill 解析器测试"""

    @pytest.fixture
    def parser(self) -> SkillParser:
        return SkillParser()

    def test_parse_valid_skill(self, parser: SkillParser) -> None:
        """测试解析有效的 Skill 内容"""
        content = """---
name: test-skill
description: A test skill for unit testing
allowed-tools: Read, Write
---

# Test Skill

This is the body content.
"""
        skill = parser.parse_content(content)

        assert skill.metadata.name == "test-skill"
        assert skill.metadata.description == "A test skill for unit testing"
        assert skill.metadata.allowed_tools == ["Read", "Write"]
        assert "This is the body content" in skill.body
        assert skill.has_tool_restrictions is True
        assert skill.tool_count == 2

    def test_parse_skill_without_tools(self, parser: SkillParser) -> None:
        """测试解析没有 allowed-tools 的 Skill"""
        content = """---
name: no-tools-skill
description: A skill without tool restrictions
---

# No Tools Skill

Body content here.
"""
        skill = parser.parse_content(content)

        assert skill.metadata.name == "no-tools-skill"
        assert skill.metadata.allowed_tools is None
        assert skill.has_tool_restrictions is False
        assert skill.tool_count == -1

    def test_parse_skill_without_frontmatter(self, parser: SkillParser) -> None:
        """测试解析没有 frontmatter 的内容"""
        content = """# Just Markdown

No frontmatter here.
"""
        skill = parser.parse_content(content)

        assert skill.metadata.name == "unnamed-skill"
        assert skill.metadata.description == ""
        assert "Just Markdown" in skill.body

    def test_parse_skill_with_list_tools(self, parser: SkillParser) -> None:
        """测试解析 YAML 列表格式的 allowed-tools"""
        content = """---
name: list-tools-skill
description: Skill with list format tools
allowed-tools:
  - Read
  - Write
  - Glob
---

Body content.
"""
        skill = parser.parse_content(content)

        assert skill.metadata.allowed_tools == ["Read", "Write", "Glob"]
        assert skill.tool_count == 3

    def test_file_hash_consistency(self, parser: SkillParser) -> None:
        """测试文件哈希的一致性"""
        content = """---
name: hash-test
description: Test hash consistency
---

Body.
"""
        skill1 = parser.parse_content(content)
        skill2 = parser.parse_content(content)

        assert skill1.file_hash == skill2.file_hash

    def test_file_hash_uniqueness(self, parser: SkillParser) -> None:
        """测试不同内容产生不同哈希"""
        content1 = """---
name: skill-1
description: First skill
---

Body 1.
"""
        content2 = """---
name: skill-2
description: Second skill
---

Body 2.
"""
        skill1 = parser.parse_content(content1)
        skill2 = parser.parse_content(content2)

        assert skill1.file_hash != skill2.file_hash

    def test_validate_skill_warnings(self, parser: SkillParser) -> None:
        """测试 Skill 验证警告"""
        content = """---
name: INVALID_NAME_WITH_CAPS
description:
---

Body.
"""
        skill = parser.parse_content(content)
        warnings = parser.validate_skill(skill)

        assert any("name" in w.lower() for w in warnings)
        assert any("description" in w.lower() for w in warnings)

    def test_parse_skill_file(self, parser: SkillParser, safe_skills_dir: Path) -> None:
        """测试从文件解析 Skill"""
        skill_file = safe_skills_dir / "basic_skill.md"

        if skill_file.exists():
            skill = parser.parse_file(skill_file)

            assert skill.source == SkillSource.LOCAL_FILE
            assert skill.metadata.name == "safe-example-skill"
            assert "Read" in skill.metadata.allowed_tools
