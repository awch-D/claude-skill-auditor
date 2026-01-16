"""CLI command interface"""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .core.parser import SkillParser, SkillParseError
from .core.audit_context import AuditResult, Severity
from .rules.engine import RuleEngine
from .reporters import get_reporter

console = Console()


def get_builtin_rules_dir() -> Path:
    """获取内置规则目录"""
    return Path(__file__).parent / "rules" / "builtin"


@click.group()
@click.version_option(version="1.0.0", prog_name="claude-skill-auditor")
@click.option("--verbose", "-v", is_flag=True, help="详细输出")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Claude Skill 安全审查工具

    用于审查第三方/开源 Claude Skill 的安全性，在引入外部 Skill 之前进行安全评估。

    示例:

        skill-auditor audit ./skill.md

        skill-auditor audit ./skill.md -o report.json -f json

        skill-auditor scan ./skills/ -r
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@cli.command()
@click.argument("skill_path", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="输出文件路径")
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["json", "markdown", "sarif"]),
    default="markdown",
    help="输出格式 (默认: markdown)"
)
@click.option(
    "--severity", "-s",
    type=click.Choice(["critical", "high", "medium", "low", "info"]),
    default="low",
    help="最低报告严重级别 (默认: low)"
)
@click.option(
    "--fail-on",
    type=click.Choice(["critical", "high", "medium", "none"]),
    default="high",
    help="导致退出码非零的最低严重级别 (默认: high)"
)
@click.option("--rules-dir", type=click.Path(exists=True), help="自定义规则目录")
@click.pass_context
def audit(
    ctx: click.Context,
    skill_path: str,
    output: Optional[str],
    output_format: str,
    severity: str,
    fail_on: str,
    rules_dir: Optional[str],
) -> None:
    """审查单个 Skill 文件

    示例:

        skill-auditor audit ./skill.md

        skill-auditor audit ./skill.md -o report.json -f json

        skill-auditor audit ./skill.md --fail-on critical
    """
    verbose = ctx.obj.get("verbose", False)
    skill_file = Path(skill_path)

    # 解析 Skill
    if verbose:
        console.print(f"[blue]正在解析 Skill 文件: {skill_file}[/blue]")

    parser = SkillParser()
    try:
        skill = parser.parse_file(skill_file)
    except SkillParseError as e:
        console.print(f"[red]解析错误: {e}[/red]")
        sys.exit(1)

    if verbose:
        console.print(f"[green]✓[/green] Skill 名称: {skill.metadata.name}")
        console.print(f"[green]✓[/green] 文件哈希: {skill.file_hash}")

    # 加载规则
    engine = RuleEngine()
    engine.load_rules_from_directory(get_builtin_rules_dir())

    if rules_dir:
        if verbose:
            console.print(f"[blue]加载自定义规则: {rules_dir}[/blue]")
        engine.load_rules_from_directory(Path(rules_dir))

    if verbose:
        console.print(f"[green]✓[/green] 已加载 {len(engine.rules)} 条规则")

    # 执行分析
    if verbose:
        console.print("[blue]正在执行静态分析...[/blue]")

    findings = engine.analyze(skill)

    # 过滤严重级别
    severity_order = ["critical", "high", "medium", "low", "info"]
    min_idx = severity_order.index(severity)
    filtered_findings = [
        f for f in findings
        if severity_order.index(f.severity.value) <= min_idx
    ]

    # 创建审计结果
    result = AuditResult(skill=skill, findings=filtered_findings)

    # 生成报告
    reporter = get_reporter(output_format)
    report = reporter.generate(result)

    if output:
        Path(output).write_text(report, encoding="utf-8")
        console.print(f"[green]✓[/green] 报告已保存至: {output}")
    else:
        console.print(report)

    # 输出摘要
    _print_summary(result, verbose)

    # 决定退出码
    if fail_on != "none":
        fail_idx = severity_order.index(fail_on)
        should_fail = any(
            severity_order.index(f.severity.value) <= fail_idx
            for f in filtered_findings
        )
        if should_fail:
            console.print(
                f"\n[red]✗[/red] 发现 {fail_on.upper()} 或更高级别的风险，审查未通过"
            )
            sys.exit(1)

    console.print("\n[green]✓[/green] 审查完成")


@cli.command()
@click.argument("directory", type=click.Path(exists=True))
@click.option("--recursive", "-r", is_flag=True, help="递归扫描子目录")
@click.option("--output", "-o", type=click.Path(), help="输出目录")
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["json", "markdown", "sarif"]),
    default="json",
    help="输出格式 (默认: json)"
)
@click.pass_context
def scan(
    ctx: click.Context,
    directory: str,
    recursive: bool,
    output: Optional[str],
    output_format: str,
) -> None:
    """批量扫描目录中的 Skill 文件

    示例:

        skill-auditor scan ./skills/

        skill-auditor scan ./skills/ -r -o ./reports/
    """
    verbose = ctx.obj.get("verbose", False)
    dir_path = Path(directory)

    # 查找所有 .md 文件
    pattern = "**/*.md" if recursive else "*.md"
    skill_files = list(dir_path.glob(pattern))

    # 过滤出有效的 Skill 文件（包含 frontmatter）
    valid_skills = []
    for f in skill_files:
        content = f.read_text(encoding="utf-8")
        if content.strip().startswith("---"):
            valid_skills.append(f)

    console.print(f"[blue]找到 {len(valid_skills)} 个 Skill 文件[/blue]")

    if not valid_skills:
        console.print("[yellow]未找到有效的 Skill 文件[/yellow]")
        return

    # 创建输出目录
    if output:
        output_dir = Path(output)
        output_dir.mkdir(parents=True, exist_ok=True)

    # 加载规则
    engine = RuleEngine()
    engine.load_rules_from_directory(get_builtin_rules_dir())

    parser = SkillParser()
    results_summary = []

    for skill_file in valid_skills:
        console.print(f"[blue]扫描: {skill_file.name}[/blue]")

        try:
            skill = parser.parse_file(skill_file)
            findings = engine.analyze(skill)
            result = AuditResult(skill=skill, findings=findings)

            results_summary.append({
                "file": str(skill_file),
                "name": skill.metadata.name,
                "risk_score": result.risk_score,
                "total_findings": result.total_findings,
                "critical": result.findings_by_severity[Severity.CRITICAL],
                "high": result.findings_by_severity[Severity.HIGH],
            })

            # 保存单个报告
            if output:
                reporter = get_reporter(output_format)
                report = reporter.generate(result)
                ext = "json" if output_format == "json" else "md" if output_format == "markdown" else "sarif"
                report_file = output_dir / f"{skill_file.stem}.{ext}"
                report_file.write_text(report, encoding="utf-8")

        except SkillParseError as e:
            console.print(f"[red]  解析错误: {e}[/red]")

    # 打印汇总表格
    _print_scan_summary(results_summary)


@cli.command()
@click.option("--output", "-o", type=click.Path(), default="skill-audit-config.yaml")
def init(output: str) -> None:
    """初始化配置文件"""
    default_config = """# Claude Skill Auditor 配置文件
version: "1.0"

# 规则配置
rules:
  # 是否启用内置规则
  builtin_enabled: true
  # 自定义规则目录
  custom_dirs: []
  # 禁用特定规则
  disabled_rules: []
  # 严重级别覆盖
  severity_overrides: {}

# 输出配置
output:
  default_format: "markdown"
  include_evidence: true
  include_recommendations: true

# CI/CD 配置
ci:
  fail_on_severity: "high"  # critical, high, medium, none
  max_risk_score: 70

# 白名单配置
whitelist:
  # 已审核通过的 Skill 文件哈希
  approved_hashes: []
"""
    Path(output).write_text(default_config, encoding="utf-8")
    console.print(f"[green]✓[/green] 配置文件已创建: {output}")


def _print_summary(result: AuditResult, verbose: bool = False) -> None:
    """打印审计摘要"""
    console.print()
    console.print("=" * 50)

    # 风险评分
    risk_color = "red" if result.risk_score >= 70 else "yellow" if result.risk_score >= 30 else "green"
    console.print(f"风险评分: [{risk_color}]{result.risk_score}/100[/{risk_color}]")
    console.print(f"发现总数: {result.total_findings}")

    # 按严重级别统计
    severity_colors = {
        Severity.CRITICAL: "red",
        Severity.HIGH: "orange1",
        Severity.MEDIUM: "yellow",
        Severity.LOW: "green",
        Severity.INFO: "blue",
    }

    for sev, count in result.findings_by_severity.items():
        if count > 0:
            color = severity_colors[sev]
            console.print(f"  - [{color}]{sev.value.upper()}[/{color}]: {count}")


def _print_scan_summary(results: list) -> None:
    """打印批量扫描汇总"""
    console.print()
    console.print("=" * 60)
    console.print("[bold]扫描汇总[/bold]")
    console.print()

    table = Table(show_header=True)
    table.add_column("Skill", style="cyan")
    table.add_column("风险评分", justify="center")
    table.add_column("发现数", justify="center")
    table.add_column("CRITICAL", justify="center", style="red")
    table.add_column("HIGH", justify="center", style="orange1")

    for r in sorted(results, key=lambda x: x["risk_score"], reverse=True):
        risk_style = "red" if r["risk_score"] >= 70 else "yellow" if r["risk_score"] >= 30 else "green"
        table.add_row(
            r["name"],
            f"[{risk_style}]{r['risk_score']}[/{risk_style}]",
            str(r["total_findings"]),
            str(r["critical"]) if r["critical"] > 0 else "-",
            str(r["high"]) if r["high"] > 0 else "-",
        )

    console.print(table)


if __name__ == "__main__":
    cli()
