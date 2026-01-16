"""Report generators"""

import json
from abc import ABC, abstractmethod

from ..core.audit_context import AuditResult, Severity


class BaseReporter(ABC):
    """报告生成器基类"""

    @property
    @abstractmethod
    def format_name(self) -> str:
        """输出格式名称"""
        pass

    @abstractmethod
    def generate(self, result: AuditResult) -> str:
        """生成报告"""
        pass


class JSONReporter(BaseReporter):
    """JSON 格式报告生成器"""

    @property
    def format_name(self) -> str:
        return "json"

    def generate(self, result: AuditResult) -> str:
        """生成 JSON 报告"""
        return json.dumps(result.to_dict(), indent=2, ensure_ascii=False)


class MarkdownReporter(BaseReporter):
    """Markdown 格式报告生成器"""

    # 严重级别图标
    SEVERITY_ICONS = {
        Severity.CRITICAL: "🔴",
        Severity.HIGH: "🟠",
        Severity.MEDIUM: "🟡",
        Severity.LOW: "🟢",
        Severity.INFO: "🔵",
    }

    @property
    def format_name(self) -> str:
        return "markdown"

    def generate(self, result: AuditResult) -> str:
        """生成 Markdown 报告"""
        lines = []

        # 标题
        lines.append("# Skill 安全审查报告")
        lines.append("")

        # 基本信息
        lines.append("## 基本信息")
        lines.append("")
        lines.append("| 属性 | 值 |")
        lines.append("|------|-----|")
        lines.append(f"| Skill 名称 | {result.skill.metadata.name} |")
        lines.append(f"| 文件路径 | {result.skill.source_path} |")
        lines.append(f"| 文件哈希 | {result.skill.file_hash} |")
        lines.append(f"| 审查时间 | {result.audit_timestamp.strftime('%Y-%m-%d %H:%M:%S')} |")
        lines.append(f"| 审查器版本 | {result.auditor_version} |")
        lines.append("")

        # 风险评估
        lines.append("## 风险评估")
        lines.append("")

        risk_indicator = (
            "🔴" if result.risk_score >= 70 else "🟡" if result.risk_score >= 30 else "🟢"
        )
        lines.append(f"- **风险评分**: {result.risk_score}/100 {risk_indicator}")

        if result.has_critical:
            lines.append("- **建议操作**: ❌ 强烈建议拒绝")
        elif result.is_blocked:
            lines.append("- **建议操作**: ⚠️ 需要人工审核")
        else:
            lines.append("- **建议操作**: ✅ 可以使用")
        lines.append("")

        # 按严重级别统计
        lines.append("### 按严重级别统计")
        lines.append("")
        lines.append("| 级别 | 数量 |")
        lines.append("|------|------|")
        for severity in Severity:
            count = result.findings_by_severity[severity]
            if count > 0:
                icon = self.SEVERITY_ICONS[severity]
                lines.append(f"| {icon} {severity.value.upper()} | {count} |")
        lines.append("")

        # 发现详情
        if result.findings:
            lines.append("## 发现详情")
            lines.append("")

            # 按严重级别排序
            sorted_findings = sorted(
                result.findings, key=lambda f: list(Severity).index(f.severity)
            )

            for finding in sorted_findings:
                icon = self.SEVERITY_ICONS[finding.severity]
                lines.append(
                    f"### {icon} {finding.severity.value.upper()}: "
                    f"{finding.rule_id or finding.id} - {finding.title}"
                )
                lines.append("")
                lines.append(f"**类别**: {finding.category.value.replace('_', ' ').title()}")
                if finding.is_ai_generated:
                    lines.append(f"**置信度**: {finding.confidence * 100:.0f}%")
                lines.append(f"**分析器**: {finding.analyzer}")
                lines.append("")
                lines.append("**描述**:")
                lines.append(finding.description)
                lines.append("")
                lines.append("**证据**:")
                lines.append("```")
                lines.append(finding.evidence[:500])
                lines.append("```")
                lines.append("")
                if finding.recommendation:
                    lines.append("**建议修复**:")
                    lines.append(finding.recommendation)
                    lines.append("")
                if finding.line_number:
                    lines.append(f"**位置**: 第 {finding.line_number} 行")
                    lines.append("")
                lines.append("---")
                lines.append("")
        else:
            lines.append("## 发现详情")
            lines.append("")
            lines.append("✅ 未发现安全问题")
            lines.append("")

        # 工具权限分析
        lines.append("## 工具权限分析")
        lines.append("")
        if result.skill.has_tool_restrictions:
            lines.append(f"- **工具数量**: {result.skill.tool_count}")
            lines.append(f"- **允许的工具**: {', '.join(result.skill.tools_list)}")
        else:
            lines.append("- **工具限制**: ⚠️ 未设置（可访问所有工具）")
        lines.append("")

        # 附录
        lines.append("## 附录")
        lines.append("")
        lines.append("### 审查规则")
        lines.append("")
        lines.append("- prompt-injection: v1.0.0")
        lines.append("- permission-abuse: v1.0.0")
        lines.append("- command-injection: v1.0.0")
        lines.append("")

        return "\n".join(lines)


class SARIFReporter(BaseReporter):
    """SARIF 格式报告生成器（GitHub Code Scanning）"""

    @property
    def format_name(self) -> str:
        return "sarif"

    def generate(self, result: AuditResult) -> str:
        """生成 SARIF 报告"""
        # SARIF 严重级别映射
        severity_map = {
            Severity.CRITICAL: "error",
            Severity.HIGH: "error",
            Severity.MEDIUM: "warning",
            Severity.LOW: "note",
            Severity.INFO: "note",
        }

        # 构建规则列表
        rules = []
        rule_ids_seen = set()
        for finding in result.findings:
            rule_id = finding.rule_id or finding.id
            if rule_id not in rule_ids_seen:
                rule_ids_seen.add(rule_id)
                rules.append(
                    {
                        "id": rule_id,
                        "name": finding.title.replace(" ", ""),
                        "shortDescription": {"text": finding.title},
                        "fullDescription": {"text": finding.description},
                        "defaultConfiguration": {"level": severity_map[finding.severity]},
                        "properties": {
                            "tags": ["security", finding.category.value],
                            "precision": "high" if finding.confidence >= 0.8 else "medium",
                        },
                    }
                )

        # 构建结果列表
        results = []
        for finding in result.findings:
            result_item = {
                "ruleId": finding.rule_id or finding.id,
                "level": severity_map[finding.severity],
                "message": {"text": f"{finding.description}: {finding.evidence[:100]}"},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {
                                "uri": result.skill.source_path,
                            },
                            "region": {
                                "startLine": finding.line_number or 1,
                                "startColumn": 1,
                                "snippet": {"text": finding.evidence[:200]},
                            },
                        }
                    }
                ],
            }
            if finding.recommendation:
                result_item["fixes"] = [{"description": {"text": finding.recommendation}}]
            results.append(result_item)

        sarif = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "claude-skill-auditor",
                            "version": result.auditor_version,
                            "informationUri": "https://github.com/your-org/claude-skill-auditor",
                            "rules": rules,
                        }
                    },
                    "results": results,
                }
            ],
        }

        return json.dumps(sarif, indent=2, ensure_ascii=False)


def get_reporter(format_name: str) -> BaseReporter:
    """获取指定格式的报告生成器"""
    reporters = {
        "json": JSONReporter(),
        "markdown": MarkdownReporter(),
        "sarif": SARIFReporter(),
    }
    if format_name not in reporters:
        raise ValueError(f"不支持的报告格式: {format_name}")
    return reporters[format_name]
