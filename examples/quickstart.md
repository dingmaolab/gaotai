# 快速开始：从零到发布

## 1. 安装

```bash
git clone https://github.com/YOUR_USER/gaotai.git
cd gaotai
pip install pyyaml
python install.py
```

## 2. 初始化账号

```bash
mkdir my-account && cd my-account
python /path/to/gaotai/gaotai.py init --name 我的公众号
```

编辑 `.gaotai/account.yaml`，填入定位、栏目、关注词。

## 3. 喂范文（可选但推荐）

把你过去写的 3-5 篇文章放进 `style/exemplars/`，然后：

```bash
python /path/to/gaotai/gaotai.py learn style/exemplars/*.md
python /path/to/gaotai/gaotai.py card-build
```

## 4. 日常使用（在对话里说就行）

| 你说 | Agent 做什么 |
|---|---|
| "记一下 xxx" | `note` → 存灵感 |
| "今天有什么可写" | `hot` → 抓热点 + 筛选 |
| "写一篇关于 xxx 的文章" | `new` → 判断维度 → 选路径 → 创作 |
| "审一下这篇" | `check` + `tone` → 分级反馈 |
| "学一下我这次的修改" | `learn draft.md final.md` → diff → lesson |
| "导出" | `send` → paste.html + zip |

## 5. 发布

打开 `export/wechat/paste.html` → 点「复制到公众号」→ 去编辑器 Ctrl+V。

**绝不自动发布。** 你始终掌握最终决定权。