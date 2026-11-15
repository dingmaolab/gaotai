# AGENTS.md — 稿台项目 Agent 指引

## 项目概述

稿台是一个**自媒体内容生产系统**，以 Agent Skill + Python CLI 的形式交付。
核心理念：**skill 负责判断，脚本负责记录。**

- 唯一 skill：`skills/gaotai/SKILL.md`（中文创作方法论）
- CLI 入口：`gaotai.py`（15 个命令，输出 JSON）
- 核心逻辑：`core/*.py`（纯 Python，依赖仅 PyYAML）
- 规则数据：`core/dimensions.yaml` + `core/structures.yaml`
- 排版主题：`themes/*.yaml`

## 架构原则

### 1. 六维度正交，不枚举文体

任何文章 = source × urgency × audience × intent × format × style 的组合。
加新内容类型 **零代码改动**。规则全在 YAML 里。

### 2. 三条路径，不固定流程

| urgency | 路径 | 步骤数 |
|---|---|---|
| hour | flash | 4 |
| day | fast | 5 |
| none | full | 9 |

默认 fast。用户不说"认真写"就不走 full。

### 3. 审稿分级，不一刀切

- **blocker**：广告法、编造、无来源硬事实、错别字 → 必须改
- **warn**：套话密度、字数超限 → 建议改
- **info**：数字密度、人称占比 → 仅供参考

软建议绝不拦截。排查词表不是自动禁词表。

### 4. 风格学习严格分流

- 自己的文章 → `learn_from_own()` → 更新 DNA
- 别人的文章 → `learn_from_reference()` → 只存 references，**不动 DNA**
- 改稿对比 → `learn_from_diff()` → 抽 lesson

### 5. 一个账号一个目录

`cd` 进账号目录就是给这个号干活。不需要 `--account` 参数。
`init` 默认把当前目录建成账号目录（`.gaotai/account.yaml` 在根）；
显式 `--vault` / `GAOTAI_VAULT` 才走传统多账号库布局（`accounts/<id>/`）。
`resolve_vault` 会从 cwd 向上找账号目录，子目录里也能干活。
源码和内容完全分离。升级代码不碰内容。

## 渐进式上下文加载

**不要一次读完所有文件。** 按需加载：

| 你要做什么 | 读什么 | 不读什么 |
|---|---|---|
| 了解项目 | AGENTS.md（本文件） | core/*.py, themes/ |
| 改规则/约束 | core/dimensions.yaml | core/*.py |
| 加结构原型 | core/structures.yaml | core/*.py |
| 改排版主题 | themes/xxx.yaml | core/format.py |
| 改审稿逻辑 | core/check.py | tone.py, format.py |
| 改AI味检测 | core/tone.py | check.py, format.py |
| 改创作方法论 | skills/gaotai/SKILL.md | core/*.py |
| 改CLI命令 | gaotai.py | core/*.py（除非涉及新函数） |
| 修bug | 相关 core/*.py + tests/test_core.py | 其他模块 |
| 加测试 | tests/test_core.py | 生产代码（除非需要理解接口） |

**每个 core/*.py 的 docstring 说明了「什么时候需要读我」。**

## 目录结构

```
gaotai/
├── gaotai.py              # CLI 入口
├── install.py             # 安装到 Claude Code / Cursor / WorkBuddy 等 Agent 环境
├── uninstall.py           # 卸载（只删技能，不碰内容）
├── skills/gaotai/SKILL.md          # 唯一 skill
├── core/
│   ├── dimensions.yaml    # 六维度规则
│   ├── structures.yaml    # 16 种结构原型
│   ├── vault.py           # 内容库 + 账号
│   ├── check.py           # 分级审稿
│   ├── tone.py            # AI 味检测
│   ├── format.py          # 微信排版
│   ├── export.py          # 发布包
│   ├── hot.py             # Playwright 抓热点
│   ├── cover.py           # 封面/卡片渲染
│   ├── style.py           # DNA 六层 + 学习
│   ├── md.py              # Markdown 解析
│   └── themes.py          # 主题加载
├── themes/*.yaml          # 6 套排版主题
├── covers/*.yaml          # 配图规格（平台×形式）
├── tests/test_core.py     # 14 项测试
└── docs/                  # 设计文档
```

## 开发约定

### 代码风格

- Python 3.10+，type hints 全覆盖
- 函数级 docstring，说明"为什么"而非"做什么"
- YAML 是规则数据，Python 是执行逻辑。**新增约束改 YAML，不改代码**
- 所有 CLI 输出 JSON，失败时 `{ok: false, code, message}`

### 测试

```bash
python -X utf8 tests/test_core.py
```

14 项测试覆盖：vault init、note、check blocker、check soft、tone、style own/ref、format、export、dimensions/structures YAML 校验、evolve、热点筛选打分、热点提取双布局（离线）。

新增功能必须加对应测试。

### 不可违反的纪律

1. **不编造**：没来源的数字不写，没核实的事实不写成肯定句
2. **不越权**：风格硬规则必须用户确认；不自动发布
3. **不啰嗦**：记灵感就是一个命令
4. **材料决定能说到哪**：材料不足就收窄判断
5. **编辑不改事实强度**："可能有效"不能润色成"已经有效"
6. **作者仍是说话的人**：不因命中词库删除个人表达

### 微信排版红线

- 不用 `<style>/<script>/<div>/<link>` → 用 `<section>/<span>/<p>`
- 不用 class/id
- 不用 position/float/grid/flex/@media/CSS 变量
- 所有样式内联
- 文字包在 `<span leaf="">` 里
- 外链转脚注
- 图片用占位符
- 深色模式用 `data-darkmode-color/bgcolor/bordercolor`

### 配图规格

按平台×形式查 `covers/*.yaml`，字号随尺寸缩放（系数制），字数超限降字号最多 2 次再截断。
deviceScaleFactor=2 出高清图。

## 参考项目

| 项目 | 借鉴了什么 |
|---|---|
| gracker/gracker-writing | "结构为内容服务"、"排查词表不是禁词表"、规则分层按需加载 |
| larashero3-dotcom/writing-dna-skill | DNA 六层蒸馏、结构模板按类型分类 |
| MaydayV/wechat-article-skill | 主题→结构映射、反重复规则、content-safety 硬事实/软观点 |
| anthropics/skills/doc-coauthoring | 三阶段协作、读者测试、逐节精炼 |
| doocs/md | 微信排版红线验证 |

## 常见任务

### 加一个新结构原型

编辑 `core/structures.yaml`，加一条含 name/beats/suits/note 的记录。不改代码。

### 加一个新的维度约束

编辑 `core/dimensions.yaml` 对应维度下的取值。不改代码。

### 加一套排版主题

在 `themes/` 下新建 YAML，包含 id/name/roles/body/h2/quote/code。不改代码。

### 修改审稿阈值

编辑 `core/dimensions.yaml` 的 format 或 soft_defaults 段。账号级 overrides 优先。

### 调试热点抓取

```bash
python gaotai.py hot --fetch-only   # 只抓不筛，看 raw 数据
python gaotai.py hot --refilter     # 从已有 raw 重筛
```

需要 `pip install playwright && playwright install chromium`。