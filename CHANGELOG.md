# Changelog

本文件记录稿台的所有版本变更。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 待办
- covers 模板 HTML 文件（当前 cover.py 内联生成，后续可抽为独立模板）
- hot.py Playwright 抓取的实际端到端测试
- 多账号并行抓取优化
- story-bank 与创作流程的自动集成（写稿时自动加载相关素材）

## [0.3.0] - 2026-11-14

### 新增
- **六维度正交架构**：source × urgency × audience × intent × format × style，任何文体都是组合，零代码扩展
- **三条创作路径**：flash / fast / full，按 urgency 自动选择
- **分级审稿**：硬底线（blocker）/ 软建议（warn）/ 个人偏好（info），软建议绝不拦截
- **16 种结构原型**：替代固定节结构，按 intent 选候选，反重复检查
- **DNA 六层风格蒸馏**：语言 / 结构 / 选题 / 素材 / 认知 / 视觉
- **持续迭代机制**：recent_articles 追踪 + story-bank 素材库 + DNA 防漂移
- **风格学习分流**：自己的文章更新 DNA，别人的文章只存 references
- **配图规格系统**：按平台×形式查 YAML，字号系数制缩放
- **安装/卸载脚本**：自动检测 Claude Code / Cursor / WorkBuddy 等 Agent 环境
- **AGENTS.md / CLAUDE.md**：Agent 开发指引，CLAUDE.md 用 @AGENTS.md 引用
- 12 项核心测试全通过

### 架构决策
- 纯 Python 重写，移除全部 TypeScript / Node.js 依赖
- skill 负责判断，脚本负责记录
- 一个账号一个目录，源码与内容完全分离
- shared/raw 存全量热点，账号各自筛选
- 参考项目实证：gracker-writing / writing-dna-skill / mayday-wechat-article / doc-coauthoring

