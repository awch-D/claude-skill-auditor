"""Skill file parser"""

import re
from pathlib import Path
from typing import Any

import yaml

from .skill import Skill, SkillMetadata, SkillSource


class SkillParseError(Exception):
    """Skill 解析错误"""

    pass


class SkillParser:
    """Skill 文件解析器"""

    # YAML frontmatter 正则模式
    FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)

    def parse_file(self, file_path: Path) -> Skill:
        """解析本地 Skill 文件"""
        if not file_path.exists():
            raise SkillParseError(f"文件不存在: {file_path}")

        if not file_path.is_file():
            raise SkillParseError(f"路径不是文件: {file_path}")

        raw_content = file_path.read_text(encoding="utf-8")

        return self.parse_content(
            raw_content,
            source=SkillSource.LOCAL_FILE,
            source_path=str(file_path.absolute()),
        )

    def parse_content(
        self,
        content: str,
        source: SkillSource = SkillSource.LOCAL_FILE,
        source_path: str = "unknown",
    ) -> Skill:
        """解析 Skill 内容"""
        raw_content = content

        # 解析 frontmatter 和 body
        frontmatter_dict, body = self._parse_frontmatter(content)

        # 创建 metadata
        metadata = SkillMetadata.from_dict(frontmatter_dict)

        return Skill(
            source=source,
            source_path=source_path,
            metadata=metadata,
            body=body,
            raw_content=raw_content,
        )

    def _parse_frontmatter(self, content: str) -> tuple[dict[str, Any], str]:
        """解析 YAML frontmatter 和 Markdown body"""
        # 检查是否以 --- 开头
        if not content.strip().startswith("---"):
            # 没有 frontmatter，整个内容作为 body
            return {}, content

        # 匹配 frontmatter
        match = self.FRONTMATTER_PATTERN.match(content)

        if not match:
            # 格式不正确，可能缺少结束的 ---
            # 尝试手动解析
            lines = content.splitlines()
            if lines[0].strip() == "---":
                # 查找结束的 ---
                end_idx = None
                for i, line in enumerate(lines[1:], start=1):
                    if line.strip() == "---":
                        end_idx = i
                        break

                if end_idx:
                    frontmatter_lines = lines[1:end_idx]
                    body_lines = lines[end_idx + 1 :]

                    frontmatter_str = "\n".join(frontmatter_lines)
                    body = "\n".join(body_lines)

                    try:
                        frontmatter_dict = yaml.safe_load(frontmatter_str) or {}
                    except yaml.YAMLError as e:
                        raise SkillParseError(f"YAML 解析错误: {e}") from e

                    return frontmatter_dict, body.strip()

            # 无法解析，返回空 frontmatter
            return {}, content

        # 正常解析
        frontmatter_str = match.group(1)
        body = content[match.end() :].strip()

        try:
            frontmatter_dict = yaml.safe_load(frontmatter_str) or {}
        except yaml.YAMLError as e:
            raise SkillParseError(f"YAML 解析错误: {e}") from e

        return frontmatter_dict, body

    def validate_skill(self, skill: Skill) -> list[str]:
        """验证 Skill 是否符合规范，返回警告列表"""
        warnings = []

        # 检查必需字段
        if not skill.metadata.name:
            warnings.append("缺少 'name' 字段")
        elif len(skill.metadata.name) > 64:
            warnings.append("'name' 字段超过 64 字符限制")
        elif not re.match(r"^[a-z0-9-]+$", skill.metadata.name):
            warnings.append("'name' 字段应只包含小写字母、数字和连字符")

        if not skill.metadata.description:
            warnings.append("缺少 'description' 字段")
        elif len(skill.metadata.description) > 1024:
            warnings.append("'description' 字段超过 1024 字符限制")

        # 检查 body 长度
        body_lines = len(skill.body.splitlines())
        if body_lines > 500:
            warnings.append(f"Body 行数 ({body_lines}) 超过建议的 500 行")

        return warnings
