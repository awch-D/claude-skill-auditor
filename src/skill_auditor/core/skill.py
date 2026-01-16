"""Skill data models"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib


class SkillSource(Enum):
    """Skill 来源类型"""
    LOCAL_FILE = "local_file"
    GITHUB_URL = "github_url"
    REGISTRY = "registry"


@dataclass
class SkillMetadata:
    """Skill YAML frontmatter 元数据"""
    name: str
    description: str
    allowed_tools: Optional[List[str]] = None
    raw_frontmatter: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillMetadata":
        """从字典创建 SkillMetadata"""
        allowed_tools = None

        # 解析 allowed-tools 字段
        tools_value = data.get("allowed-tools") or data.get("allowed_tools")
        if tools_value:
            if isinstance(tools_value, str):
                # 解析 "tool1, tool2" 格式
                allowed_tools = [t.strip() for t in tools_value.split(",") if t.strip()]
            elif isinstance(tools_value, list):
                allowed_tools = [str(t).strip() for t in tools_value if t]

        return cls(
            name=data.get("name", "unnamed-skill"),
            description=data.get("description", ""),
            allowed_tools=allowed_tools,
            raw_frontmatter=data,
        )


@dataclass
class Skill:
    """Skill 完整数据模型"""
    source: SkillSource
    source_path: str  # 文件路径或 URL
    metadata: SkillMetadata
    body: str  # Markdown 正文内容
    raw_content: str  # 原始文件内容

    # 计算属性（延迟初始化）
    file_hash: str = field(default="", init=False)
    line_count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        """初始化计算属性"""
        self.file_hash = hashlib.sha256(self.raw_content.encode()).hexdigest()[:16]
        self.line_count = len(self.raw_content.splitlines())

    @property
    def has_tool_restrictions(self) -> bool:
        """是否有工具限制"""
        return self.metadata.allowed_tools is not None

    @property
    def tool_count(self) -> int:
        """工具数量，-1 表示无限制"""
        if self.metadata.allowed_tools is not None:
            return len(self.metadata.allowed_tools)
        return -1

    @property
    def tools_list(self) -> List[str]:
        """返回工具列表（空列表表示无限制）"""
        return self.metadata.allowed_tools or []

    def get_line_content(self, line_number: int) -> str:
        """获取指定行的内容"""
        lines = self.raw_content.splitlines()
        if 1 <= line_number <= len(lines):
            return lines[line_number - 1]
        return ""
