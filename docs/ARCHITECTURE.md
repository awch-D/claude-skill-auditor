# Claude Skill Auditor - Architecture

## System Architecture Diagram

```mermaid
flowchart TB
    subgraph CLI["CLI Layer (cli.py)"]
        direction TB
        CMD_AUDIT["audit<br/>单文件审计"]
        CMD_SCAN["scan<br/>目录扫描"]
        CMD_SCANALL["scan-all<br/>自动发现扫描"]
        CMD_PATHS["paths<br/>路径显示"]
        CMD_INIT["init<br/>配置初始化"]
    end

    subgraph CORE["Core Layer (core/)"]
        direction TB
        PARSER["SkillParser<br/>parser.py"]
        SKILL["Skill Model<br/>skill.py"]
        AUDIT_CTX["AuditResult<br/>audit_context.py"]
    end

    subgraph RULES["Rules Engine (rules/)"]
        direction TB
        ENGINE["RuleEngine<br/>engine.py"]
        subgraph BUILTIN["Built-in Rules (builtin/)"]
            R_PI["prompt_injection.yaml<br/>Prompt注入检测"]
            R_PERM["permissions.yaml<br/>权限滥用检测"]
            R_CMD["commands.yaml<br/>命令注入检测"]
            R_FMT["format_compliance.yaml<br/>格式合规检测"]
        end
    end

    subgraph REPORTERS["Reporters (reporters/)"]
        direction TB
        JSON_RPT["JSON Reporter"]
        MD_RPT["Markdown Reporter"]
        SARIF_RPT["SARIF Reporter"]
    end

    subgraph DISCOVERY["Path Discovery"]
        direction TB
        PATHS_DETECT["get_claude_skill_paths()"]
        SKILL_FIND["find_skill_files()"]
        DISCOVER["discover_all_skills()"]
    end

    subgraph OUTPUT["Output"]
        CONSOLE["Console<br/>(Rich)"]
        FILE["File Output"]
    end

    %% CLI to Discovery
    CMD_SCANALL --> DISCOVER
    CMD_SCAN --> PATHS_DETECT
    CMD_PATHS --> PATHS_DETECT

    %% Discovery to Core
    DISCOVER --> SKILL_FIND
    PATHS_DETECT --> SKILL_FIND
    SKILL_FIND --> PARSER

    %% CLI to Core
    CMD_AUDIT --> PARSER

    %% Core flow
    PARSER --> SKILL
    SKILL --> ENGINE
    ENGINE --> AUDIT_CTX

    %% Rules
    ENGINE --> R_PI
    ENGINE --> R_PERM
    ENGINE --> R_CMD
    ENGINE --> R_FMT

    %% Audit to Reporters
    AUDIT_CTX --> JSON_RPT
    AUDIT_CTX --> MD_RPT
    AUDIT_CTX --> SARIF_RPT

    %% Output
    JSON_RPT --> FILE
    MD_RPT --> FILE
    SARIF_RPT --> FILE
    MD_RPT --> CONSOLE
    CMD_PATHS --> CONSOLE
    CMD_INIT --> FILE
```

## Component Description

### CLI Layer (`cli.py`)
| Component | Description |
|-----------|-------------|
| `audit` | 审计单个 Skill 文件 |
| `scan` | 扫描指定目录或标准位置 |
| `scan-all` | 自动发现并扫描所有 Claude Skill |
| `paths` | 显示当前系统的 Skill 路径 |
| `init` | 创建配置文件 |

### Core Layer (`core/`)
| Component | File | Description |
|-----------|------|-------------|
| `SkillParser` | `parser.py` | 解析 YAML frontmatter + Markdown |
| `Skill` | `skill.py` | Skill 数据模型 |
| `AuditResult` | `audit_context.py` | 审计结果和风险评分 |

### Rules Engine (`rules/`)
| Component | Description |
|-----------|-------------|
| `RuleEngine` | 规则加载、条件注册、分析执行 |
| `prompt_injection.yaml` | 检测忽略指令、角色操纵等 |
| `permissions.yaml` | 检测权限滥用、危险工具 |
| `commands.yaml` | 检测危险命令、路径遍历 |
| `format_compliance.yaml` | 检测格式合规问题 |

### Reporters (`reporters/`)
| Format | Use Case |
|--------|----------|
| JSON | 自动化处理、API 集成 |
| Markdown | 人工阅读、文档 |
| SARIF | GitHub Code Scanning |

## Data Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Discovery
    participant Parser
    participant Engine
    participant Reporter

    User->>CLI: skill-auditor scan-all
    CLI->>Discovery: discover_all_skills()
    Discovery->>Discovery: get_claude_skill_paths()
    Discovery->>Discovery: find_skill_files()
    Discovery-->>CLI: [skill_files]

    loop For each skill file
        CLI->>Parser: parse_file(path)
        Parser-->>CLI: Skill object
        CLI->>Engine: analyze(skill)
        Engine->>Engine: apply rules
        Engine-->>CLI: [findings]
        CLI->>CLI: create AuditResult
    end

    CLI->>Reporter: generate(result)
    Reporter-->>CLI: report string
    CLI-->>User: Display/Save report
```

## Directory Structure

```
claude-skill-auditor/
├── src/skill_auditor/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                 # CLI 入口和命令定义
│   ├── core/
│   │   ├── __init__.py
│   │   ├── parser.py          # Skill 文件解析器
│   │   ├── skill.py           # Skill 数据模型
│   │   └── audit_context.py   # 审计结果模型
│   ├── rules/
│   │   ├── __init__.py
│   │   ├── engine.py          # 规则引擎
│   │   └── builtin/           # 内置规则
│   │       ├── prompt_injection.yaml
│   │       ├── permissions.yaml
│   │       ├── commands.yaml
│   │       └── format_compliance.yaml
│   └── reporters/
│       └── __init__.py        # 报告生成器
├── tests/                     # 测试套件
├── .github/workflows/         # CI/CD
├── README.md                  # English
├── README_zh.md               # 中文
└── pyproject.toml             # 包配置
```

## Security Rule Categories

```mermaid
mindmap
  root((Security Rules))
    Prompt Injection
      Ignore Instructions
      Role Manipulation
      Hidden Commands
      Context Switching
    Data Exfiltration
      External URLs
      Webhooks
      Bulk Collection
    Command Injection
      Shell Commands
      Package Managers
      Curl Pipes
    Credential Exposure
      ENV Variables
      API Keys
      Hardcoded Secrets
    Permission Abuse
      Unrestricted Tools
      Dangerous Combos
    Path Traversal
      Sensitive Dirs
      Config Files
      SSH Keys
    Social Engineering
      Urgency Tactics
      Authority Claims
```

## Risk Scoring

```
Risk Score = Σ (Severity Weight × Finding Count)

Severity Weights:
  CRITICAL = 25
  HIGH     = 15
  MEDIUM   = 8
  LOW      = 3
  INFO     = 1

Max Score = 100
```
