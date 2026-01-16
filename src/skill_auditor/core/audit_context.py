"""Audit context and result models"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
import uuid


class Severity(Enum):
    """风险严重等级"""
    CRITICAL = "critical"  # 必须阻断
    HIGH = "high"          # 强烈建议阻断
    MEDIUM = "medium"      # 需要人工审核
    LOW = "low"            # 信息提示
    INFO = "info"          # 纯信息

    @classmethod
    def from_string(cls, value: str) -> "Severity":
        """从字符串创建 Severity"""
        return cls(value.lower())

    def __lt__(self, other: "Severity") -> bool:
        order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]
        return order.index(self) < order.index(other)


class RiskCategory(Enum):
    """风险类别"""
    PROMPT_INJECTION = "prompt_injection"
    PERMISSION_ABUSE = "permission_abuse"
    DATA_EXFILTRATION = "data_exfiltration"
    COMMAND_INJECTION = "command_injection"
    PATH_TRAVERSAL = "path_traversal"
    CREDENTIAL_EXPOSURE = "credential_exposure"
    SOCIAL_ENGINEERING = "social_engineering"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, value: str) -> "RiskCategory":
        """从字符串创建 RiskCategory"""
        try:
            return cls(value.lower())
        except ValueError:
            return cls.UNKNOWN


@dataclass
class Finding:
    """单个发现项"""
    id: str  # 唯一标识符 e.g., "PI-001"
    category: RiskCategory
    severity: Severity
    title: str
    description: str
    evidence: str  # 触发该发现的原文片段
    line_number: Optional[int] = None
    recommendation: str = ""
    rule_id: Optional[str] = None  # 触发的规则 ID
    confidence: float = 1.0  # AI 分析时的置信度 0-1

    # 元数据
    analyzer: str = "unknown"  # 产生该发现的分析器名称
    is_ai_generated: bool = False  # 是否由 AI 语义分析产生

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "evidence": self.evidence,
            "line_number": self.line_number,
            "recommendation": self.recommendation,
            "rule_id": self.rule_id,
            "confidence": self.confidence,
            "analyzer": self.analyzer,
            "is_ai_generated": self.is_ai_generated,
        }


@dataclass
class AuditResult:
    """完整审计结果"""
    skill: "Skill"  # Forward reference
    findings: List[Finding] = field(default_factory=list)

    # 审计元信息
    audit_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    audit_timestamp: datetime = field(default_factory=datetime.now)
    auditor_version: str = "1.0.0"
    config_hash: str = ""  # 配置文件哈希，用于可复现性

    @property
    def total_findings(self) -> int:
        """发现总数"""
        return len(self.findings)

    @property
    def findings_by_severity(self) -> Dict[Severity, int]:
        """按严重级别统计"""
        result = {s: 0 for s in Severity}
        for f in self.findings:
            result[f.severity] += 1
        return result

    @property
    def findings_by_category(self) -> Dict[RiskCategory, int]:
        """按类别统计"""
        result = {c: 0 for c in RiskCategory}
        for f in self.findings:
            result[f.category] += 1
        return result

    @property
    def is_blocked(self) -> bool:
        """是否应该阻断（存在 CRITICAL 或 HIGH）"""
        return any(
            f.severity in [Severity.CRITICAL, Severity.HIGH]
            for f in self.findings
        )

    @property
    def has_critical(self) -> bool:
        """是否存在 CRITICAL 级别问题"""
        return any(f.severity == Severity.CRITICAL for f in self.findings)

    @property
    def risk_score(self) -> int:
        """风险评分 0-100"""
        weights = {
            Severity.CRITICAL: 40,
            Severity.HIGH: 25,
            Severity.MEDIUM: 10,
            Severity.LOW: 3,
            Severity.INFO: 0,
        }
        score = sum(weights[f.severity] for f in self.findings)
        return min(100, score)

    def get_findings_by_severity(self, severity: Severity) -> List[Finding]:
        """获取指定严重级别的发现"""
        return [f for f in self.findings if f.severity == severity]

    def get_findings_by_category(self, category: RiskCategory) -> List[Finding]:
        """获取指定类别的发现"""
        return [f for f in self.findings if f.category == category]

    def filter_by_min_severity(self, min_severity: Severity) -> List[Finding]:
        """过滤出严重级别 >= min_severity 的发现"""
        severity_order = [
            Severity.CRITICAL,
            Severity.HIGH,
            Severity.MEDIUM,
            Severity.LOW,
            Severity.INFO,
        ]
        min_idx = severity_order.index(min_severity)
        return [
            f for f in self.findings
            if severity_order.index(f.severity) <= min_idx
        ]

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "audit_id": self.audit_id,
            "audit_timestamp": self.audit_timestamp.isoformat(),
            "auditor_version": self.auditor_version,
            "skill": {
                "name": self.skill.metadata.name,
                "source": self.skill.source.value,
                "source_path": self.skill.source_path,
                "file_hash": self.skill.file_hash,
                "line_count": self.skill.line_count,
                "has_tool_restrictions": self.skill.has_tool_restrictions,
                "tool_count": self.skill.tool_count,
                "tools": self.skill.tools_list,
            },
            "summary": {
                "total_findings": self.total_findings,
                "risk_score": self.risk_score,
                "is_blocked": self.is_blocked,
                "by_severity": {k.value: v for k, v in self.findings_by_severity.items()},
                "by_category": {k.value: v for k, v in self.findings_by_category.items()},
            },
            "findings": [f.to_dict() for f in self.findings],
        }


# Import for type hint
from .skill import Skill  # noqa: E402
