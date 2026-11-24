# Changelog

本文件记录稿台的所有版本变更。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增
- **工具课闸门（--tool-course）**：check 新增工具课模式——工具本体（`## ①`..`## 跟做步骤`，剔除表格/图片/代码块后纯汉字）超 1500 字出 warn；全文 0 图 0 表出 warn；定位不到本体降级 info 不硬拦；计数口径写死在 _tool_body 注释与测试里，不留人裁（依据：账号仓《工具课整改方案》R1/R2/R3）。三库同步：core/check.py 字节一致，SKILL.md 两处说明，回归测试 test_check_tool_course（16/16 过）
- **skill 自包含安装**：install.py 把 SKILL.md + 完整运行时（gaotai.py/core/themes/covers）一起装进技能目录，装完不依赖源码仓库位置
- **一个账号一个目录落地**：init 默认把当前目录建成账号目录；resolve_vault 从 cwd 向上找账号，子目录里也能干活；显式 --vault / GAOTAI_VAULT 才走多账号库布局
- SKILL.md 增加「运行环境」节：CLI 绝对路径约定、工作目录、Python 要求

### 修复
- **export.zip 坏包**：`_build_zip` 中央目录记录漏写文件名字节（zip 无法被任何标准工具打开），且文件名缺 UTF-8 标志位（中文名解出乱码）；test_export 增加 zip 可解析 + 内容一致性回归断言
- init 不再误落到 ~/GaotaiVault（原先在任意目录 init 都会污染默认库）
- Vault.exists() 兼容单账号布局（无 vault.yaml 也识别）

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

