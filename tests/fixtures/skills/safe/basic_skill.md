---
name: safe-example-skill
description: 一个安全的示例 Skill，用于演示正确的 Skill 编写方式
allowed-tools: Read, Glob, Grep
---

# 安全示例 Skill

这是一个安全的 Skill 示例，展示了正确的编写方式。

## 功能说明

此 Skill 用于搜索和读取代码文件。

## 使用步骤

1. 使用 Glob 工具查找匹配的文件
2. 使用 Read 工具读取文件内容
3. 使用 Grep 工具搜索特定模式

## 注意事项

- 仅读取项目目录内的文件
- 不执行任何写入操作
- 不访问敏感配置文件
