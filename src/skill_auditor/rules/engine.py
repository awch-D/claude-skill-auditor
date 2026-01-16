"""Rule engine for static analysis"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

from ..core.skill import Skill
from ..core.audit_context import Finding, Severity, RiskCategory


@dataclass
class Rule:
    """单条规则"""
    id: str
    name: str
    severity: Severity
    category: RiskCategory
    description: str
    patterns: Optional[List[str]] = None  # 正则模式
    condition: Optional[str] = None       # 条件表达式
    recommendation: str = ""
    enabled: bool = True
    examples: List[str] = field(default_factory=list)

    # 编译后的正则模式
    _compiled_patterns: List[re.Pattern] = field(default_factory=list, repr=False)

    def compile_patterns(self) -> None:
        """编译正则模式"""
        if self.patterns:
            self._compiled_patterns = []
            for p in self.patterns:
                try:
                    compiled = re.compile(p, re.MULTILINE | re.IGNORECASE)
                    self._compiled_patterns.append(compiled)
                except re.error as e:
                    print(f"警告: 规则 {self.id} 的正则模式编译失败: {p} - {e}")

    def match(self, text: str) -> List[Dict[str, Any]]:
        """返回所有匹配项及其位置"""
        matches = []
        if self._compiled_patterns:
            for pattern in self._compiled_patterns:
                for m in pattern.finditer(text):
                    # 计算行号
                    line_number = text[:m.start()].count("\n") + 1
                    matches.append({
                        "match": m.group(),
                        "start": m.start(),
                        "end": m.end(),
                        "line": line_number,
                    })
        return matches


# 条件函数注册表
CONDITION_REGISTRY: Dict[str, Callable[[Skill, Any], bool]] = {}


def register_condition(name: str):
    """条件装饰器"""
    def decorator(func: Callable[[Skill, Any], bool]):
        CONDITION_REGISTRY[name] = func
        return func
    return decorator


# 内置条件
@register_condition("no_allowed_tools")
def check_no_allowed_tools(skill: Skill, params: Any) -> bool:
    """检查是否没有工具限制"""
    return not skill.has_tool_restrictions


@register_condition("has_critical_tools")
def check_has_critical_tools(skill: Skill, params: Any) -> bool:
    """检查是否包含高危工具"""
    critical_tools = ["bash", "shell", "terminal", "execute", "cmd"]
    if skill.metadata.allowed_tools:
        return any(
            t.lower() in critical_tools
            for t in skill.metadata.allowed_tools
        )
    return False


@register_condition("tool_count")
def check_tool_count(skill: Skill, params: str) -> bool:
    """检查工具数量条件，params: "> 10", "< 5" 等"""
    import operator
    ops = {
        ">": operator.gt,
        "<": operator.lt,
        ">=": operator.ge,
        "<=": operator.le,
        "==": operator.eq,
    }
    for op_str, op_func in ops.items():
        if op_str in params:
            threshold = int(params.replace(op_str, "").strip())
            return skill.tool_count >= 0 and op_func(skill.tool_count, threshold)
    return False


@register_condition("has_tool_combination")
def check_tool_combination(skill: Skill, params: str) -> bool:
    """检查是否同时包含多个工具，params: "Bash,WebFetch" """
    required_tools = [t.strip().lower() for t in params.split(",")]
    if skill.metadata.allowed_tools:
        allowed_lower = [t.lower() for t in skill.metadata.allowed_tools]
        return all(rt in allowed_lower for rt in required_tools)
    return False


@register_condition("body_length_exceeds")
def check_body_length(skill: Skill, params: Any) -> bool:
    """检查 body 长度是否超过阈值"""
    return len(skill.body) > int(params)


@register_condition("description_has_angle_brackets")
def check_description_angle_brackets(skill: Skill, params: Any) -> bool:
    """检查 description 是否包含 < 或 >（违反官方规范）"""
    desc = skill.metadata.description
    return "<" in desc or ">" in desc


@register_condition("name_invalid_format")
def check_name_invalid_format(skill: Skill, params: Any) -> bool:
    """检查 name 是否符合官方规范（小写字母、数字、连字符）"""
    import re
    name = skill.metadata.name
    if not name:
        return True
    if not re.match(r"^[a-z0-9-]+$", name):
        return True
    if name.startswith("-") or name.endswith("-") or "--" in name:
        return True
    return False


@register_condition("description_length_exceeds")
def check_description_length(skill: Skill, params: Any) -> bool:
    """检查 description 长度是否超过阈值"""
    return len(skill.metadata.description) > int(params)


class RuleEngine:
    """规则引擎"""

    def __init__(self) -> None:
        self.rules: Dict[str, Rule] = {}
        self.rule_sets: Dict[str, Dict] = {}
        self._dangerous_tools: Dict[str, List[str]] = {
            "critical": ["bash", "shell", "terminal", "execute", "cmd"],
            "high": ["write", "edit", "delete", "filewrite"],
            "medium": ["webfetch", "websearch"],
        }

    def load_rules_from_directory(self, directory: Path) -> None:
        """加载目录下所有 YAML 规则文件"""
        if not directory.exists():
            return

        for yaml_file in directory.glob("*.yaml"):
            self.load_rules_from_file(yaml_file)

    def load_rules_from_file(self, file_path: Path) -> None:
        """加载单个规则文件"""
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            return

        rule_set = data.get("rule_set", {})
        set_id = rule_set.get("id", file_path.stem)
        self.rule_sets[set_id] = rule_set

        # 加载危险工具列表
        if "dangerous_tools" in data:
            for level, tools in data["dangerous_tools"].items():
                if level in self._dangerous_tools:
                    self._dangerous_tools[level].extend(tools)
                else:
                    self._dangerous_tools[level] = tools

        # 加载规则
        for rule_data in data.get("rules", []):
            rule = Rule(
                id=rule_data["id"],
                name=rule_data["name"],
                severity=Severity.from_string(rule_data["severity"]),
                category=RiskCategory.from_string(rule_data["category"]),
                description=rule_data["description"],
                patterns=rule_data.get("patterns"),
                condition=rule_data.get("condition"),
                recommendation=rule_data.get("recommendation", ""),
                enabled=rule_data.get("enabled", True),
                examples=rule_data.get("examples", []),
            )
            rule.compile_patterns()
            self.rules[rule.id] = rule

    def analyze(self, skill: Skill) -> List[Finding]:
        """对 Skill 执行所有规则分析"""
        findings = []

        for rule_id, rule in self.rules.items():
            if not rule.enabled:
                continue

            # 模式匹配
            if rule.patterns:
                # 检查 frontmatter 原始内容
                frontmatter_str = str(skill.metadata.raw_frontmatter)
                matches = rule.match(frontmatter_str)
                for m in matches:
                    findings.append(self._create_finding(rule, m, "frontmatter"))

                # 检查 body
                matches = rule.match(skill.body)
                for m in matches:
                    findings.append(self._create_finding(rule, m, "body"))

                # 检查 description
                matches = rule.match(skill.metadata.description)
                for m in matches:
                    findings.append(self._create_finding(rule, m, "description"))

            # 条件检查
            if rule.condition:
                condition_finding = self._evaluate_condition(rule, skill)
                if condition_finding:
                    findings.append(condition_finding)

        return findings

    def _create_finding(self, rule: Rule, match: Dict, location: str) -> Finding:
        """从规则匹配创建 Finding"""
        return Finding(
            id=f"{rule.id}-{match.get('line', 0)}",
            category=rule.category,
            severity=rule.severity,
            title=rule.name,
            description=rule.description,
            evidence=match["match"][:200],  # 截断证据
            line_number=match.get("line"),
            recommendation=rule.recommendation,
            rule_id=rule.id,
            analyzer="static_rule_engine",
        )

    def _evaluate_condition(self, rule: Rule, skill: Skill) -> Optional[Finding]:
        """评估条件规则"""
        condition = rule.condition
        if not condition:
            return None

        # 解析条件名称和参数
        # 格式: "condition_name" 或 "condition_name:params"
        if ":" in condition:
            cond_name, params = condition.split(":", 1)
        else:
            cond_name = condition
            params = None

        # 查找并执行条件函数
        if cond_name in CONDITION_REGISTRY:
            try:
                result = CONDITION_REGISTRY[cond_name](skill, params)
                if result:
                    return self._create_condition_finding(rule, skill)
            except Exception as e:
                print(f"警告: 条件 {cond_name} 执行失败: {e}")

        return None

    def _create_condition_finding(self, rule: Rule, skill: Skill) -> Finding:
        """从条件检查创建 Finding"""
        # 生成具体的证据
        evidence = self._generate_condition_evidence(rule, skill)

        return Finding(
            id=rule.id,
            category=rule.category,
            severity=rule.severity,
            title=rule.name,
            description=rule.description,
            evidence=evidence,
            recommendation=rule.recommendation,
            rule_id=rule.id,
            analyzer="static_rule_engine",
        )

    def _generate_condition_evidence(self, rule: Rule, skill: Skill) -> str:
        """生成条件检查的证据说明"""
        condition = rule.condition or ""

        if "no_allowed_tools" in condition:
            return "Skill 未定义 allowed-tools 限制"

        if "has_critical_tools" in condition:
            critical = [
                t for t in skill.tools_list
                if t.lower() in self._dangerous_tools.get("critical", [])
            ]
            return f"Skill 请求访问高危工具: {', '.join(critical)}"

        if "tool_count" in condition:
            return f"工具数量 ({skill.tool_count}) 超过阈值"

        if "has_tool_combination" in condition:
            return f"Skill 同时请求工具组合: {', '.join(skill.tools_list)}"

        return f"条件检查触发: {condition}"

    def disable_rule(self, rule_id: str) -> None:
        """禁用指定规则"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False

    def enable_rule(self, rule_id: str) -> None:
        """启用指定规则"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True

    def override_severity(self, rule_id: str, severity: Severity) -> None:
        """覆盖规则严重级别"""
        if rule_id in self.rules:
            self.rules[rule_id].severity = severity
