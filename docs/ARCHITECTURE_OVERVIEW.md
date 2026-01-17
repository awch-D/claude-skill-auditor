# Claude Skill Auditor - Architecture Overview

## System Architecture

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#ffffff', 'primaryTextColor': '#000000', 'primaryBorderColor': '#000000', 'lineColor': '#000000', 'secondaryColor': '#f5f5f5', 'tertiaryColor': '#ffffff', 'background': '#ffffff', 'mainBkg': '#ffffff', 'nodeBorder': '#000000', 'clusterBkg': '#f9f9f9', 'clusterBorder': '#000000', 'titleColor': '#000000', 'edgeLabelBackground': '#ffffff'}}}%%
flowchart TB
    subgraph Input
        SkillFile[Skill File .md]
        Directory[Directory Path]
        AutoDiscovery[Auto Discovery]
    end

    subgraph CLI[Command Line Interface]
        audit[audit]
        scan[scan]
        scan-all[scan-all]
        paths[paths]
        init[init]
    end

    subgraph PathDiscovery[Path Discovery Module]
        GetPaths[get_claude_skill_paths]
        FindFiles[find_skill_files]
        DiscoverAll[discover_all_skills]
    end

    subgraph Core[Core Processing]
        Parser[SkillParser]
        SkillModel[Skill Data Model]
        RuleEngine[Rule Engine]
        AuditResult[Audit Result]
    end

    subgraph Rules[Security Rules]
        PromptInjection[prompt_injection.yaml]
        Permissions[permissions.yaml]
        Commands[commands.yaml]
        FormatCompliance[format_compliance.yaml]
    end

    subgraph Output[Report Output]
        JSON[JSON Reporter]
        Markdown[Markdown Reporter]
        SARIF[SARIF Reporter]
        Console[Console Output]
    end

    %% Input Flow
    SkillFile --> audit
    Directory --> scan
    AutoDiscovery --> scan-all

    %% CLI to Path Discovery
    scan-all --> DiscoverAll
    scan --> GetPaths
    paths --> GetPaths
    DiscoverAll --> FindFiles
    GetPaths --> FindFiles

    %% Path Discovery to Core
    FindFiles --> Parser
    audit --> Parser

    %% Core Processing Flow
    Parser --> SkillModel
    SkillModel --> RuleEngine

    %% Rule Engine to Rules
    RuleEngine --> PromptInjection
    RuleEngine --> Permissions
    RuleEngine --> Commands
    RuleEngine --> FormatCompliance

    %% Rules back to Result
    PromptInjection --> AuditResult
    Permissions --> AuditResult
    Commands --> AuditResult
    FormatCompliance --> AuditResult

    %% Output Generation
    AuditResult --> JSON
    AuditResult --> Markdown
    AuditResult --> SARIF
    AuditResult --> Console
```

---

## Data Flow

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#ffffff', 'primaryTextColor': '#000000', 'primaryBorderColor': '#000000', 'lineColor': '#000000', 'secondaryColor': '#f5f5f5', 'background': '#ffffff', 'actorBkg': '#ffffff', 'actorBorder': '#000000', 'actorTextColor': '#000000', 'actorLineColor': '#000000', 'signalColor': '#000000', 'signalTextColor': '#000000', 'labelBoxBkgColor': '#ffffff', 'labelBoxBorderColor': '#000000', 'labelTextColor': '#000000', 'loopTextColor': '#000000', 'noteBkgColor': '#f5f5f5', 'noteTextColor': '#000000', 'noteBorderColor': '#000000'}}}%%
sequenceDiagram
    autonumber

    participant User
    participant CLI
    participant Discovery
    participant Parser
    participant RuleEngine
    participant Reporter

    User->>CLI: Execute Command

    alt scan-all / scan
        CLI->>Discovery: Discover Skills
        Discovery->>Discovery: Get Platform Paths
        Discovery->>Discovery: Find Skill Files
        Discovery-->>CLI: File List
    end

    loop Each Skill File
        CLI->>Parser: Parse File
        Parser->>Parser: Extract YAML Frontmatter
        Parser->>Parser: Parse Markdown Body
        Parser-->>CLI: Skill Object

        CLI->>RuleEngine: Analyze Skill
        RuleEngine->>RuleEngine: Pattern Matching
        RuleEngine->>RuleEngine: Condition Checks
        RuleEngine-->>CLI: Findings List
    end

    CLI->>CLI: Calculate Risk Score
    CLI->>Reporter: Generate Report
    Reporter-->>CLI: Report String
    CLI-->>User: Output Result
```

---

## Module Structure

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#ffffff', 'primaryTextColor': '#000000', 'primaryBorderColor': '#000000', 'lineColor': '#000000', 'secondaryColor': '#f5f5f5', 'background': '#ffffff', 'nodeBorder': '#000000', 'clusterBkg': '#f9f9f9', 'clusterBorder': '#000000'}}}%%
flowchart LR
    subgraph Package[skill_auditor]
        direction TB

        subgraph CLI_Module[cli.py]
            Commands[CLI Commands]
            PathDiscovery[Path Discovery]
        end

        subgraph Core_Module[core/]
            parser[parser.py]
            skill[skill.py]
            audit_context[audit_context.py]
        end

        subgraph Rules_Module[rules/]
            engine[engine.py]
            builtin[builtin/*.yaml]
        end

        subgraph Reporters_Module[reporters/]
            reporters[__init__.py]
        end
    end

    Commands --> parser
    PathDiscovery --> parser
    parser --> skill
    skill --> engine
    engine --> builtin
    engine --> audit_context
    audit_context --> reporters
```

---

## Security Rule Categories

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#ffffff', 'primaryTextColor': '#000000', 'lineColor': '#000000', 'secondaryColor': '#f5f5f5', 'background': '#ffffff'}}}%%
flowchart TB
    subgraph Categories[Security Rule Categories]
        direction TB

        subgraph Critical[CRITICAL Severity]
            PI[Prompt Injection]
            DE[Data Exfiltration]
            CI[Command Injection]
            CE[Credential Exposure]
        end

        subgraph High[HIGH Severity]
            PA[Permission Abuse]
            PT[Path Traversal]
        end

        subgraph Medium[MEDIUM Severity]
            SE[Social Engineering]
            FC[Format Compliance]
        end
    end

    PI --> PI1[Ignore Instructions]
    PI --> PI2[Role Manipulation]
    PI --> PI3[Hidden Commands]

    DE --> DE1[External URLs]
    DE --> DE2[Webhooks]
    DE --> DE3[Bulk Collection]

    CI --> CI1[Shell Commands]
    CI --> CI2[Package Managers]
    CI --> CI3[Curl Pipes]

    CE --> CE1[ENV Variables]
    CE --> CE2[API Keys]
    CE --> CE3[Hardcoded Secrets]

    PA --> PA1[Unrestricted Tools]
    PA --> PA2[Dangerous Combinations]

    PT --> PT1[Sensitive Directories]
    PT --> PT2[Config Files]
    PT --> PT3[SSH Keys]

    SE --> SE1[Urgency Tactics]
    SE --> SE2[Authority Claims]
```

---

## Risk Scoring

```
Risk Score Calculation
======================

Formula: Risk Score = min(100, Σ(Weight × Count))

Severity Weights:
┌──────────────┬────────┐
│   Severity   │ Weight │
├──────────────┼────────┤
│   CRITICAL   │   40   │
│   HIGH       │   25   │
│   MEDIUM     │   10   │
│   LOW        │    3   │
│   INFO       │    0   │
└──────────────┴────────┘

Risk Levels:
┌──────────────┬─────────────┐
│    Level     │    Range    │
├──────────────┼─────────────┤
│  HIGH RISK   │  >= 70      │
│  MEDIUM RISK │  30 - 69    │
│  LOW RISK    │  < 30       │
└──────────────┴─────────────┘
```

---

## Directory Structure

```
claude-skill-auditor/
├── src/skill_auditor/
│   ├── __init__.py              # Package exports
│   ├── __main__.py              # Entry point
│   ├── cli.py                   # CLI commands + path discovery
│   │
│   ├── core/
│   │   ├── parser.py            # YAML + Markdown parser
│   │   ├── skill.py             # Skill data model
│   │   └── audit_context.py     # Audit result model
│   │
│   ├── rules/
│   │   ├── engine.py            # Rule engine
│   │   └── builtin/
│   │       ├── prompt_injection.yaml
│   │       ├── permissions.yaml
│   │       ├── commands.yaml
│   │       └── format_compliance.yaml
│   │
│   └── reporters/
│       └── __init__.py          # JSON, Markdown, SARIF
│
├── tests/                       # Test suite
├── docs/                        # Documentation
└── pyproject.toml               # Package configuration
```

---

## Platform Paths

```
┌──────────────┬─────────────────────────────────┬─────────────────────┐
│   Platform   │      Personal Skills Path       │  Project Skills     │
├──────────────┼─────────────────────────────────┼─────────────────────┤
│    macOS     │  ~/.claude/skills/              │  ./.claude/skills/  │
│    Linux     │  ~/.claude/skills/              │  ./.claude/skills/  │
│   Windows    │  %USERPROFILE%\.claude\skills\  │  .\.claude\skills\  │
└──────────────┴─────────────────────────────────┴─────────────────────┘
```
