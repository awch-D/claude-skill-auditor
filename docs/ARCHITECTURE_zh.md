# Claude Skill Auditor - 架构文档

<p align="center">
  <a href="ARCHITECTURE.md">English</a> | <a href="ARCHITECTURE_zh.md">中文</a>
</p>

---

## 系统架构图

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'primaryColor': '#000000', 'primaryTextColor': '#ffffff', 'primaryBorderColor': '#ffffff', 'lineColor': '#ffffff', 'secondaryColor': '#1a1a1a', 'tertiaryColor': '#2a2a2a', 'background': '#000000', 'mainBkg': '#000000', 'nodeBorder': '#ffffff', 'clusterBkg': '#1a1a1a', 'clusterBorder': '#ffffff', 'titleColor': '#ffffff', 'edgeLabelBackground': '#000000'}}}%%
flowchart TB
    subgraph INPUT["📥 输入"]
        direction TB
        FILE["Skill 文件<br/>(.md)"]
        DIR["目录<br/>扫描"]
        AUTO["自动<br/>发现"]
    end

    subgraph CLI["🖥️ CLI 层"]
        direction TB
        CMD_AUDIT["audit<br/>单文件审计"]
        CMD_SCAN["scan<br/>目录扫描"]
        CMD_SCANALL["scan-all<br/>自动发现"]
        CMD_PATHS["paths<br/>路径显示"]
    end

    subgraph DISCOVERY["🔍 路径发现"]
        direction TB
        PATHS_FUNC["get_claude_skill_paths()<br/>获取标准路径"]
        FIND_FUNC["find_skill_files()<br/>查找文件"]
        DISCOVER_FUNC["discover_all_skills()<br/>发现所有技能"]
    end

    subgraph CORE["⚙️ 核心引擎"]
        direction TB
        PARSER["SkillParser<br/>YAML + Markdown 解析"]
        SKILL_MODEL["Skill Model<br/>数据结构"]
        RULE_ENGINE["RuleEngine<br/>规则匹配"]
        AUDIT_RESULT["AuditResult<br/>风险评分"]
    end

    subgraph RULES["📋 安全规则"]
        direction TB
        R1["prompt_injection.yaml<br/>Prompt 注入"]
        R2["permissions.yaml<br/>权限滥用"]
        R3["commands.yaml<br/>命令注入"]
        R4["format_compliance.yaml<br/>格式合规"]
    end

    subgraph OUTPUT["📤 输出"]
        direction TB
        JSON_OUT["JSON<br/>自动化处理"]
        MD_OUT["Markdown<br/>人工阅读"]
        SARIF_OUT["SARIF<br/>GitHub 集成"]
        CONSOLE_OUT["Console<br/>终端显示"]
    end

    %% 输入到 CLI
    FILE --> CMD_AUDIT
    DIR --> CMD_SCAN
    AUTO --> CMD_SCANALL

    %% CLI 到路径发现
    CMD_SCANALL --> DISCOVER_FUNC
    CMD_SCAN --> PATHS_FUNC
    CMD_PATHS --> PATHS_FUNC
    DISCOVER_FUNC --> FIND_FUNC
    PATHS_FUNC --> FIND_FUNC

    %% 路径发现到核心
    FIND_FUNC --> PARSER
    CMD_AUDIT --> PARSER

    %% 核心流程
    PARSER --> SKILL_MODEL
    SKILL_MODEL --> RULE_ENGINE
    RULE_ENGINE --> R1
    RULE_ENGINE --> R2
    RULE_ENGINE --> R3
    RULE_ENGINE --> R4
    RULE_ENGINE --> AUDIT_RESULT

    %% 输出
    AUDIT_RESULT --> JSON_OUT
    AUDIT_RESULT --> MD_OUT
    AUDIT_RESULT --> SARIF_OUT
    AUDIT_RESULT --> CONSOLE_OUT
```

---

## 数据流

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'primaryColor': '#000000', 'primaryTextColor': '#ffffff', 'primaryBorderColor': '#ffffff', 'lineColor': '#ffffff', 'secondaryColor': '#1a1a1a', 'tertiaryColor': '#2a2a2a', 'background': '#000000', 'actorBkg': '#1a1a1a', 'actorBorder': '#ffffff', 'actorTextColor': '#ffffff', 'actorLineColor': '#ffffff', 'signalColor': '#ffffff', 'signalTextColor': '#ffffff', 'labelBoxBkgColor': '#000000', 'labelBoxBorderColor': '#ffffff', 'labelTextColor': '#ffffff', 'loopTextColor': '#ffffff', 'noteBkgColor': '#1a1a1a', 'noteTextColor': '#ffffff', 'noteBorderColor': '#ffffff', 'activationBkgColor': '#2a2a2a', 'activationBorderColor': '#ffffff', 'sequenceNumberColor': '#ffffff'}}}%%
sequenceDiagram
    autonumber
    participant U as 👤 用户
    participant C as 🖥️ CLI
    participant D as 🔍 路径发现
    participant P as 📄 解析器
    participant E as ⚙️ 规则引擎
    participant R as 📋 规则库
    participant O as 📤 报告生成

    U->>C: skill-auditor scan-all

    rect rgb(30, 30, 30)
        Note over C,D: 路径发现阶段
        C->>D: discover_all_skills()
        D->>D: get_claude_skill_paths()
        D->>D: find_skill_files()
        D-->>C: skill_files[]
    end

    rect rgb(30, 30, 30)
        Note over C,E: 分析阶段
        loop 遍历每个 Skill 文件
            C->>P: parse_file(path)
            P->>P: 提取 YAML frontmatter
            P->>P: 解析 Markdown body
            P-->>C: Skill 对象

            C->>E: analyze(skill)
            E->>R: 加载规则
            R-->>E: 规则模式
            E->>E: 模式匹配
            E->>E: 条件检查
            E-->>C: findings[]
        end
    end

    rect rgb(30, 30, 30)
        Note over C,O: 报告生成阶段
        C->>C: 创建 AuditResult
        C->>C: 计算风险评分
        C->>O: generate(result)
        O-->>C: 报告字符串
    end

    C-->>U: 显示/保存报告
```

---

## 组件架构

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'primaryColor': '#000000', 'primaryTextColor': '#ffffff', 'primaryBorderColor': '#ffffff', 'lineColor': '#ffffff', 'secondaryColor': '#1a1a1a', 'tertiaryColor': '#2a2a2a', 'background': '#000000', 'nodeBorder': '#ffffff', 'clusterBkg': '#1a1a1a', 'clusterBorder': '#ffffff', 'titleColor': '#ffffff'}}}%%
flowchart LR
    subgraph pkg["📦 skill_auditor"]
        direction TB

        subgraph cli_mod["cli.py - 命令行接口"]
            CLI_MAIN["@cli.group()<br/>主入口"]
            CLI_AUDIT["audit<br/>单文件审计"]
            CLI_SCAN["scan<br/>目录扫描"]
            CLI_SCANALL["scan-all<br/>自动发现"]
            CLI_PATHS["paths<br/>路径显示"]
        end

        subgraph core_mod["core/ - 核心模块"]
            PARSER_MOD["parser.py<br/>文件解析器"]
            SKILL_MOD["skill.py<br/>数据模型"]
            AUDIT_MOD["audit_context.py<br/>审计结果"]
        end

        subgraph rules_mod["rules/ - 规则模块"]
            ENGINE_MOD["engine.py<br/>规则引擎"]
            subgraph builtin["builtin/ - 内置规则"]
                YAML1["*.yaml"]
            end
        end

        subgraph reporters_mod["reporters/ - 报告模块"]
            BASE_RPT["BaseReporter"]
            JSON_RPT["JSONReporter"]
            MD_RPT["MarkdownReporter"]
            SARIF_RPT["SARIFReporter"]
        end
    end

    CLI_MAIN --> CLI_AUDIT
    CLI_MAIN --> CLI_SCAN
    CLI_MAIN --> CLI_SCANALL
    CLI_MAIN --> CLI_PATHS

    CLI_AUDIT --> PARSER_MOD
    CLI_SCAN --> PARSER_MOD
    CLI_SCANALL --> PARSER_MOD

    PARSER_MOD --> SKILL_MOD
    SKILL_MOD --> ENGINE_MOD
    ENGINE_MOD --> YAML1
    ENGINE_MOD --> AUDIT_MOD

    AUDIT_MOD --> BASE_RPT
    BASE_RPT --> JSON_RPT
    BASE_RPT --> MD_RPT
    BASE_RPT --> SARIF_RPT
```

---

## 安全规则类别

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'primaryColor': '#000000', 'primaryTextColor': '#ffffff', 'lineColor': '#ffffff', 'secondaryColor': '#1a1a1a'}}}%%
mindmap
  root((🛡️ 安全规则))
    🎭 Prompt 注入
      忽略指令
      角色操纵
      隐藏命令
      上下文切换
    📤 数据泄露
      外部 URL
      Webhook
      批量收集
    💻 命令注入
      Shell 命令
      包管理器
      Curl 管道
    🔑 凭证暴露
      环境变量
      API 密钥
      硬编码密钥
    ⚠️ 权限滥用
      无限制工具
      危险组合
    📁 路径遍历
      敏感目录
      配置文件
      SSH 密钥
    🎭 社会工程
      紧迫感操纵
      权威冒充
```

---

## 风险评分模型

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'primaryColor': '#000000', 'primaryTextColor': '#ffffff', 'primaryBorderColor': '#ffffff', 'lineColor': '#ffffff', 'pie1': '#dc3545', 'pie2': '#fd7e14', 'pie3': '#ffc107', 'pie4': '#28a745', 'pie5': '#17a2b8', 'pieTitleTextColor': '#ffffff', 'pieSectionTextColor': '#ffffff', 'pieLegendTextColor': '#ffffff'}}}%%
pie showData
    title 严重级别权重分布
    "严重 CRITICAL (40)" : 40
    "高危 HIGH (25)" : 25
    "中危 MEDIUM (10)" : 10
    "低危 LOW (3)" : 3
    "信息 INFO (0)" : 2
```

### 评分公式

```
┌─────────────────────────────────────────────────────────────┐
│                      风险评分计算                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   风险评分 = Σ (严重级别权重 × 发现数量)                      │
│                                                             │
│   ┌──────────────┬────────────┬─────────────────────────┐  │
│   │   严重级别   │    权重    │         影响            │  │
│   ├──────────────┼────────────┼─────────────────────────┤  │
│   │   严重       │     40     │  必须阻断安装            │  │
│   │   高危       │     25     │  强烈建议阻断            │  │
│   │   中危       │     10     │  需要人工审核            │  │
│   │   低危       │      3     │  信息提示                │  │
│   │   信息       │      0     │  无需操作                │  │
│   └──────────────┴────────────┴─────────────────────────┘  │
│                                                             │
│   最高评分: 100                                             │
│                                                             │
│   风险等级:                                                 │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  🔴 高风险     │  评分 >= 70                        │  │
│   │  🟡 中风险     │  评分 30-69                        │  │
│   │  🟢 低风险     │  评分 < 30                         │  │
│   └─────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 目录结构

```
claude-skill-auditor/
├── src/skill_auditor/
│   ├── __init__.py           # 包导出
│   ├── __main__.py           # 入口点
│   ├── cli.py                # CLI 命令和路径发现
│   ├── core/
│   │   ├── __init__.py
│   │   ├── parser.py         # YAML + Markdown 解析器
│   │   ├── skill.py          # Skill 数据模型
│   │   └── audit_context.py  # 审计结果和发现
│   ├── rules/
│   │   ├── __init__.py
│   │   ├── engine.py         # 规则引擎和条件
│   │   └── builtin/          # 内置 YAML 规则
│   │       ├── prompt_injection.yaml
│   │       ├── permissions.yaml
│   │       ├── commands.yaml
│   │       └── format_compliance.yaml
│   └── reporters/
│       └── __init__.py       # JSON, Markdown, SARIF
├── tests/                    # 测试套件
├── docs/                     # 文档
├── .github/workflows/        # CI/CD
├── README.md                 # 英文文档
├── README_zh.md              # 中文文档
└── pyproject.toml            # 包配置
```

---

## 平台支持

| 平台 | 个人技能路径 | 项目技能路径 |
|------|-------------|-------------|
| **macOS** | `~/.claude/skills/` | `./.claude/skills/` |
| **Linux** | `~/.claude/skills/` | `./.claude/skills/` |
| **Windows** | `%USERPROFILE%\.claude\skills\` | `.\.claude\skills\` |

---

## CI/CD 集成

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'primaryColor': '#000000', 'primaryTextColor': '#ffffff', 'primaryBorderColor': '#ffffff', 'lineColor': '#ffffff', 'secondaryColor': '#1a1a1a', 'tertiaryColor': '#2a2a2a', 'background': '#000000', 'nodeBorder': '#ffffff', 'clusterBkg': '#1a1a1a', 'clusterBorder': '#ffffff'}}}%%
flowchart LR
    subgraph trigger["🎯 触发器"]
        PUSH["Push 推送"]
        PR["Pull Request"]
    end

    subgraph ci["⚡ CI 流水线"]
        CHECKOUT["检出代码"]
        SETUP["配置 Python"]
        INSTALL["安装审计工具"]
        AUDIT["运行审计"]
        SARIF["生成 SARIF"]
    end

    subgraph output["📊 结果"]
        PASS["✅ 通过"]
        FAIL["❌ 失败"]
        SECURITY["🔒 GitHub<br/>安全标签"]
    end

    PUSH --> CHECKOUT
    PR --> CHECKOUT
    CHECKOUT --> SETUP
    SETUP --> INSTALL
    INSTALL --> AUDIT
    AUDIT --> SARIF
    AUDIT -->|"评分 < 阈值"| PASS
    AUDIT -->|"评分 >= 阈值"| FAIL
    SARIF --> SECURITY
```
