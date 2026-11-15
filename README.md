# 稿台

自媒体内容生产系统。**一套 skill + Python CLI，不需要插件。**

- 热点和灵感落成 markdown
- 六维度正交架构，任何文体都是组合，零改动扩展
- 三条创作路径（flash / fast / full），按 urgency 自动选
- 分级审稿：硬底线拦截，软建议只提示
- DNA 六层风格蒸馏，从你的修改里持续学习
- 导出可直接粘贴的公众号/小红书发布包

## 安装

```bash
python install.py
```

自动检测 Claude Code / Cursor / WorkBuddy 等 Agent 环境并安装技能。
skill 自包含：SKILL.md + 完整 CLI 运行时一起装进技能目录，装完不依赖源码仓库位置。

## 使用

一个账号一个目录。建个目录 cd 进去，在对话里说「初始化」即可；手动等价命令：

```bash
cd /path/to/my-account
python <技能目录>/gaotai.py init --name 另起炉录
```

然后在对话里说话就行：

- "记一下 xxx" → 记灵感
- "今天有什么可写" → 抓热点
- "写一篇 xxx" → 创作流程
- "审一下" → 审稿
- "学一下这篇" → 风格学习
- "导出" → 发布包

## 文档

| 文件 | 给谁看 |
|---|---|
| [AGENTS.md](AGENTS.md) | Agent 开发者（架构、约定、常见任务） |
| [CLAUDE.md](CLAUDE.md) | Claude Code 用户（快速上手、纪律） |
| [skills/gaotai/SKILL.md](skills/gaotai/SKILL.md) | 模型（创作方法论） |
| [docs/配图规格.md](docs/配图规格.md) | 配图尺寸矩阵 |
| [docs/多元文体自查.md](docs/多元文体自查.md) | 设计决策记录 |

## 要求

- Python ≥ 3.10
- PyYAML（`pip install pyyaml`）
- Playwright（可选，热点抓取和配图渲染需要）

## License

MIT