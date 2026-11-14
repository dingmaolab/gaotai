# 示例

本目录包含稿台的使用示例，帮助你快速理解创作流程。

## 目录

| 文件 | 说明 |
|---|---|
| `quickstart.md` | 从零开始的完整流程演示 |
| `dimensions-examples.md` | 六维度组合示例（覆盖多种文体） |
| `style-learning.md` | 风格学习分流示例 |

## 运行示例

```bash
# 1. 初始化一个测试账号
mkdir my-test-account && cd my-test-account
python /path/to/gaotai/gaotai.py init --name 测试号

# 2. 记一条灵感
python /path/to/gaotai/gaotai.py note "今天发现一个有趣的工具"

# 3. 新建项目
python /path/to/gaotai/gaotai.py new "我的第一篇测试文章"

# 4. 手动写 draft.md 后审稿
python /path/to/gaotai/gaotai.py check projects/*/draft.md

# 5. 排版预览
python /path/to/gaotai/gaotai.py format projects/*/draft.md

# 6. 导出发布包
python /path/to/gaotai/gaotai.py send projects/*/draft.md --title "测试文章"
```

> **提示**：实际使用时不需要记命令。在对话里说"记一下""写一篇""审一下"就行，Agent 会自动调用对应工具。