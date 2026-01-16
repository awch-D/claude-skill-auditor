"""CLI command interface"""

import sys
import os
from pathlib import Path
from typing import Optional, List, Tuple

# Fix Windows Unicode encoding issues
if sys.platform == "win32":
    # Set UTF-8 mode for Windows
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    # Enable UTF-8 mode via environment
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .core.parser import SkillParser, SkillParseError
from .core.audit_context import AuditResult, Severity
from .rules.engine import RuleEngine
from .reporters import get_reporter

# Configure Rich console with safe output for all platforms
console = Console(force_terminal=False, soft_wrap=True)


def get_builtin_rules_dir() -> Path:
    """获取内置规则目录"""
    return Path(__file__).parent / "rules" / "builtin"


def get_claude_skill_paths() -> dict:
    """获取 Claude Skill 的标准路径

    Returns:
        dict: 包含各类型技能路径的字典
            - personal: 个人全局技能路径
            - project: 当前项目技能路径
            - desktop_config: Claude Desktop 配置文件路径
            - desktop_logs: Claude Desktop 日志路径
    """
    home = Path.home()
    cwd = Path.cwd()

    paths = {
        "personal": None,
        "project": None,
        "desktop_config": None,
        "desktop_logs": None,
    }

    if sys.platform == "win32":
        # Windows paths
        paths["personal"] = home / ".claude" / "skills"
        paths["desktop_config"] = Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
        paths["desktop_logs"] = Path(os.environ.get("APPDATA", "")) / "Claude" / "logs"
    elif sys.platform == "darwin":
        # macOS paths
        paths["personal"] = home / ".claude" / "skills"
        paths["desktop_config"] = home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        paths["desktop_logs"] = home / "Library" / "Logs" / "Claude"
    else:
        # Linux paths (similar to macOS for CLI)
        paths["personal"] = home / ".claude" / "skills"
        paths["desktop_config"] = home / ".config" / "claude" / "claude_desktop_config.json"
        paths["desktop_logs"] = home / ".local" / "share" / "claude" / "logs"

    # Project skills (same for all platforms)
    paths["project"] = cwd / ".claude" / "skills"

    return paths


def find_skill_files(directory: Path, recursive: bool = True) -> List[Path]:
    """查找目录中的有效 Skill 文件

    Args:
        directory: 要搜索的目录
        recursive: 是否递归搜索子目录

    Returns:
        有效 Skill 文件路径列表
    """
    if not directory.exists():
        return []

    pattern = "**/*.md" if recursive else "*.md"
    skill_files = []

    for f in directory.glob(pattern):
        # 跳过常见的非 Skill 文件
        if f.name.lower() in ["readme.md", "changelog.md", "contributing.md", "license.md"]:
            continue
        try:
            content = f.read_text(encoding="utf-8")
            # 检查是否包含 YAML frontmatter
            if content.strip().startswith("---"):
                skill_files.append(f)
        except (UnicodeDecodeError, PermissionError):
            continue

    return skill_files


def discover_all_skills() -> List[Tuple[str, Path, List[Path]]]:
    """发现所有已安装的 Claude Skills

    Returns:
        List of tuples: (location_name, base_path, skill_files)
    """
    paths = get_claude_skill_paths()
    discovered = []

    # 检查个人全局技能
    if paths["personal"] and paths["personal"].exists():
        skills = find_skill_files(paths["personal"], recursive=True)
        if skills:
            discovered.append(("Personal (Global)", paths["personal"], skills))

    # 检查项目技能
    if paths["project"] and paths["project"].exists():
        skills = find_skill_files(paths["project"], recursive=True)
        if skills:
            discovered.append(("Project (Local)", paths["project"], skills))

    return discovered


@click.group()
@click.version_option(version="1.0.0", prog_name="claude-skill-auditor")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Claude Skill Security Auditor

    Audit third-party Claude Skills for security risks before installation.

    \b
    Standard Claude Skill locations:
      - Personal (Global): ~/.claude/skills/
      - Project (Local):   ./.claude/skills/

    \b
    Examples:
        skill-auditor audit ./skill.md
        skill-auditor scan --global
        skill-auditor scan --project
        skill-auditor scan-all
        skill-auditor paths
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@cli.command()
@click.argument("skill_path", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["json", "markdown", "sarif"]),
    default="markdown",
    help="Output format (default: markdown)"
)
@click.option(
    "--severity", "-s",
    type=click.Choice(["critical", "high", "medium", "low", "info"]),
    default="low",
    help="Minimum severity to report (default: low)"
)
@click.option(
    "--fail-on",
    type=click.Choice(["critical", "high", "medium", "none"]),
    default="high",
    help="Fail threshold for exit code (default: high)"
)
@click.option("--rules-dir", type=click.Path(exists=True), help="Custom rules directory")
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
    """Audit a single Skill file

    \b
    Examples:
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
@click.argument("directory", type=click.Path(exists=True), required=False)
@click.option("--recursive", "-r", is_flag=True, default=True, help="Recursive scan (default: True)")
@click.option("--output", "-o", type=click.Path(), help="Output directory")
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["json", "markdown", "sarif"]),
    default="json",
    help="Output format (default: json)"
)
@click.option("--global", "-g", "scan_global", is_flag=True, help="Scan personal global skills (~/.claude/skills/)")
@click.option("--project", "-p", "scan_project", is_flag=True, help="Scan project local skills (./.claude/skills/)")
@click.pass_context
def scan(
    ctx: click.Context,
    directory: Optional[str],
    recursive: bool,
    output: Optional[str],
    output_format: str,
    scan_global: bool,
    scan_project: bool,
) -> None:
    """Scan multiple Skill files in a directory

    \b
    You can specify a directory, or use --global/--project flags:
      skill-auditor scan ./skills/        # Scan specific directory
      skill-auditor scan --global         # Scan ~/.claude/skills/
      skill-auditor scan --project        # Scan ./.claude/skills/
      skill-auditor scan -g -p            # Scan both locations

    \b
    Examples:
        skill-auditor scan ./skills/
        skill-auditor scan ./skills/ -r -o ./reports/
        skill-auditor scan --global --project
    """
    verbose = ctx.obj.get("verbose", False)
    paths = get_claude_skill_paths()

    # Determine directories to scan
    directories_to_scan = []

    if directory:
        directories_to_scan.append(("Custom", Path(directory)))

    if scan_global:
        if paths["personal"] and paths["personal"].exists():
            directories_to_scan.append(("Personal (Global)", paths["personal"]))
        else:
            console.print(f"[yellow]Personal skills directory not found: {paths['personal']}[/yellow]")

    if scan_project:
        if paths["project"] and paths["project"].exists():
            directories_to_scan.append(("Project (Local)", paths["project"]))
        else:
            console.print(f"[yellow]Project skills directory not found: {paths['project']}[/yellow]")

    # If no directory specified and no flags, show help
    if not directories_to_scan:
        console.print("[yellow]Please specify a directory or use --global/--project flags[/yellow]")
        console.print("\nUsage examples:")
        console.print("  skill-auditor scan ./skills/")
        console.print("  skill-auditor scan --global")
        console.print("  skill-auditor scan --project")
        console.print("  skill-auditor scan -g -p")
        return

    # Load rules
    engine = RuleEngine()
    engine.load_rules_from_directory(get_builtin_rules_dir())
    parser = SkillParser()

    all_results = []

    for location_name, dir_path in directories_to_scan:
        console.print(f"\n[bold blue]Scanning: {location_name}[/bold blue]")
        console.print(f"[dim]Path: {dir_path}[/dim]")

        # Find skill files
        skill_files = find_skill_files(dir_path, recursive=recursive)

        if not skill_files:
            console.print(f"[yellow]  No valid Skill files found[/yellow]")
            continue

        console.print(f"[blue]  Found {len(skill_files)} Skill files[/blue]")

        # Create output directory
        if output:
            output_dir = Path(output)
            output_dir.mkdir(parents=True, exist_ok=True)

        for skill_file in skill_files:
            rel_path = skill_file.relative_to(dir_path) if skill_file.is_relative_to(dir_path) else skill_file.name
            console.print(f"[dim]  Scanning: {rel_path}[/dim]")

            try:
                skill = parser.parse_file(skill_file)
                findings = engine.analyze(skill)
                result = AuditResult(skill=skill, findings=findings)

                all_results.append({
                    "location": location_name,
                    "file": str(skill_file),
                    "relative_path": str(rel_path),
                    "name": skill.metadata.name,
                    "risk_score": result.risk_score,
                    "total_findings": result.total_findings,
                    "critical": result.findings_by_severity[Severity.CRITICAL],
                    "high": result.findings_by_severity[Severity.HIGH],
                })

                # Save individual report
                if output:
                    reporter = get_reporter(output_format)
                    report = reporter.generate(result)
                    ext = "json" if output_format == "json" else "md" if output_format == "markdown" else "sarif"
                    report_file = output_dir / f"{skill_file.stem}.{ext}"
                    report_file.write_text(report, encoding="utf-8")

            except SkillParseError as e:
                console.print(f"[red]    Parse error: {e}[/red]")

    # Print summary table
    if all_results:
        _print_scan_summary(all_results)


@cli.command()
@click.option("--output", "-o", type=click.Path(), default="skill-audit-config.yaml")
def init(output: str) -> None:
    """Create a configuration file"""
    default_config = """# Claude Skill Auditor Configuration
version: "1.0"

# Rule settings
rules:
  # Enable built-in rules
  builtin_enabled: true
  # Custom rules directories
  custom_dirs: []
  # Disable specific rules
  disabled_rules: []
  # Severity overrides
  severity_overrides: {}

# Output settings
output:
  default_format: "markdown"
  include_evidence: true
  include_recommendations: true

# CI/CD settings
ci:
  fail_on_severity: "high"  # critical, high, medium, none
  max_risk_score: 70

# Whitelist
whitelist:
  # Approved skill file hashes
  approved_hashes: []
"""
    Path(output).write_text(default_config, encoding="utf-8")
    console.print(f"[green]OK[/green] Config file created: {output}")


@cli.command("scan-all")
@click.option("--output", "-o", type=click.Path(), help="Output directory for reports")
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["json", "markdown", "sarif"]),
    default="json",
    help="Output format (default: json)"
)
@click.pass_context
def scan_all(ctx: click.Context, output: Optional[str], output_format: str) -> None:
    """Scan all Claude Skill locations automatically

    This command automatically discovers and scans skills from:
      - Personal (Global): ~/.claude/skills/
      - Project (Local):   ./.claude/skills/

    \b
    Examples:
        skill-auditor scan-all
        skill-auditor scan-all -o ./reports/
    """
    verbose = ctx.obj.get("verbose", False)

    console.print("[bold]Discovering Claude Skills...[/bold]\n")

    discovered = discover_all_skills()

    if not discovered:
        console.print("[yellow]No Claude Skills found in standard locations.[/yellow]")
        paths = get_claude_skill_paths()
        console.print("\nSearched locations:")
        console.print(f"  Personal: {paths['personal']}")
        console.print(f"  Project:  {paths['project']}")
        return

    # Load rules
    engine = RuleEngine()
    engine.load_rules_from_directory(get_builtin_rules_dir())
    parser = SkillParser()

    all_results = []

    for location_name, base_path, skill_files in discovered:
        console.print(f"[bold blue]{location_name}[/bold blue]")
        console.print(f"[dim]Path: {base_path}[/dim]")
        console.print(f"[blue]Found {len(skill_files)} skills[/blue]\n")

        # Create output directory
        if output:
            output_dir = Path(output)
            output_dir.mkdir(parents=True, exist_ok=True)

        for skill_file in skill_files:
            rel_path = skill_file.relative_to(base_path) if skill_file.is_relative_to(base_path) else skill_file.name
            console.print(f"[dim]  Scanning: {rel_path}[/dim]")

            try:
                skill = parser.parse_file(skill_file)
                findings = engine.analyze(skill)
                result = AuditResult(skill=skill, findings=findings)

                all_results.append({
                    "location": location_name,
                    "file": str(skill_file),
                    "relative_path": str(rel_path),
                    "name": skill.metadata.name,
                    "risk_score": result.risk_score,
                    "total_findings": result.total_findings,
                    "critical": result.findings_by_severity[Severity.CRITICAL],
                    "high": result.findings_by_severity[Severity.HIGH],
                })

                # Save individual report
                if output:
                    reporter = get_reporter(output_format)
                    report = reporter.generate(result)
                    ext = "json" if output_format == "json" else "md" if output_format == "markdown" else "sarif"
                    report_file = output_dir / f"{skill_file.stem}.{ext}"
                    report_file.write_text(report, encoding="utf-8")

            except SkillParseError as e:
                console.print(f"[red]    Parse error: {e}[/red]")

        console.print()

    # Print summary
    if all_results:
        _print_scan_summary(all_results)


@cli.command()
def paths() -> None:
    """Show Claude Skill paths for current system

    Displays the standard locations where Claude Skills are stored
    on your operating system.
    """
    paths = get_claude_skill_paths()

    console.print("[bold]Claude Skill Paths[/bold]\n")

    # Platform info
    platform_name = {
        "win32": "Windows",
        "darwin": "macOS",
        "linux": "Linux",
    }.get(sys.platform, sys.platform)
    console.print(f"Platform: [cyan]{platform_name}[/cyan]\n")

    # Skills locations
    console.print("[bold]Skill Locations:[/bold]")

    # Personal (Global)
    personal = paths["personal"]
    exists_mark = "[green]OK[/green]" if personal and personal.exists() else "[dim]not found[/dim]"
    console.print(f"  Personal (Global): {personal} {exists_mark}")

    # Project (Local)
    project = paths["project"]
    exists_mark = "[green]OK[/green]" if project and project.exists() else "[dim]not found[/dim]"
    console.print(f"  Project (Local):   {project} {exists_mark}")

    # Desktop config
    console.print("\n[bold]Claude Desktop:[/bold]")
    desktop_config = paths["desktop_config"]
    exists_mark = "[green]OK[/green]" if desktop_config and desktop_config.exists() else "[dim]not found[/dim]"
    console.print(f"  Config: {desktop_config} {exists_mark}")

    desktop_logs = paths["desktop_logs"]
    exists_mark = "[green]OK[/green]" if desktop_logs and desktop_logs.exists() else "[dim]not found[/dim]"
    console.print(f"  Logs:   {desktop_logs} {exists_mark}")

    # Quick tips
    console.print("\n[bold]Quick Commands:[/bold]")
    console.print("  skill-auditor scan --global     # Scan personal skills")
    console.print("  skill-auditor scan --project    # Scan project skills")
    console.print("  skill-auditor scan-all          # Scan all locations")


def _print_summary(result: AuditResult, verbose: bool = False) -> None:
    """Print audit summary"""
    console.print()
    console.print("=" * 50)

    # Risk score
    risk_color = "red" if result.risk_score >= 70 else "yellow" if result.risk_score >= 30 else "green"
    console.print(f"Risk Score: [{risk_color}]{result.risk_score}/100[/{risk_color}]")
    console.print(f"Total Findings: {result.total_findings}")

    # By severity
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
    """Print batch scan summary"""
    console.print()
    console.print("=" * 70)
    console.print("[bold]Scan Summary[/bold]")
    console.print()

    table = Table(show_header=True)
    table.add_column("Location", style="dim")
    table.add_column("Skill", style="cyan")
    table.add_column("Risk", justify="center")
    table.add_column("Issues", justify="center")
    table.add_column("CRIT", justify="center", style="red")
    table.add_column("HIGH", justify="center", style="orange1")

    for r in sorted(results, key=lambda x: x["risk_score"], reverse=True):
        risk_style = "red" if r["risk_score"] >= 70 else "yellow" if r["risk_score"] >= 30 else "green"
        location = r.get("location", "")[:12]  # Truncate location name
        table.add_row(
            location,
            r["name"],
            f"[{risk_style}]{r['risk_score']}[/{risk_style}]",
            str(r["total_findings"]),
            str(r["critical"]) if r["critical"] > 0 else "-",
            str(r["high"]) if r["high"] > 0 else "-",
        )

    console.print(table)

    # Summary stats
    total_skills = len(results)
    high_risk = sum(1 for r in results if r["risk_score"] >= 70)
    medium_risk = sum(1 for r in results if 30 <= r["risk_score"] < 70)
    low_risk = sum(1 for r in results if r["risk_score"] < 30)

    console.print(f"\nTotal: {total_skills} skills | ", end="")
    console.print(f"[red]High Risk: {high_risk}[/red] | ", end="")
    console.print(f"[yellow]Medium: {medium_risk}[/yellow] | ", end="")
    console.print(f"[green]Low: {low_risk}[/green]")


if __name__ == "__main__":
    cli()
