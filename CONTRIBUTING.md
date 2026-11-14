# 贡献指南

感谢你对稿台的兴趣！以下是参与贡献的方式。

## 快速开始

```bash
git clone https://github.com/YOUR_USER/gaotai.git
cd gaotai
pip install -e ".[dev]"
python -X utf8 tests/test_core.py
```

## 什么可以贡献

| 类型 | 改哪里 | 需要改代码吗 |
|---|---|---|
| 新结构原型 | `core/structures.yaml` | ❌ |
| 新维度约束 | `core/dimensions.yaml` | ❌ |
| 新排版主题 | `themes/xxx.yaml` | ❌ |
| 新配图规格 | `covers/xxx.yaml` | ❌ |
| 审稿词表扩充 | `core/check.py` AD_LAW / CONFUSIONS | ✅ |
| AI 味新模式 | `core/tone.py` PATTERNS | ✅ |
| Bug 修复 | `core/*.py` | ✅ |
| 文档改进 | `docs/` / `README.md` / `AGENTS.md` | ❌ |

**优先级：YAML > Python。** 能用数据解决的不要改代码。

## 提交规范

### Commit Message

```
<type>(<scope>): <简短描述>

[可选正文]
```

type: `feat` / `fix` / `docs` / `refactor` / `test` / `chore`
scope: `core` / `skill` / `themes` / `covers` / `cli` / `docs`

示例：
```
feat(core): 新增 diary 结构原型
fix(check): 修复广告法豁免正则漏匹配
docs: 补充配图规格说明
```

### Pull Request

1. Fork → 新建分支 → 改动 → 测试通过 → PR
2. PR 标题遵循 commit 规范
3. 描述里说明：**改了什么、为什么改、怎么验证**
4. 新增功能必须加测试
5. YAML 改动不需要测试，但请确认格式正确（`python -c "import yaml; yaml.safe_load(open('file.yaml'))"`）

## 不可违反的纪律

1. **不编造**：没来源的数字不写，没核实的事实不写成肯定句
2. **不越权**：风格硬规则必须用户确认；不自动发布
3. **材料决定能说到哪**：材料不足就收窄判断
4. **编辑不改事实强度**："可能有效"不能润色成"已经有效"
5. **作者仍是说话的人**：不因命中词库删除个人表达
6. **排查词表不是自动禁词表**：套话检测只提示，不拦截

## 版本发布流程

1. 更新 `CHANGELOG.md`（把 Unreleased 移到新版本号下）
2. 更新 `pyproject.toml` 版本号
3. 跑测试：`python -X utf8 tests/test_core.py`
4. Tag：`git tag v0.x.0 && git push --tags`
5. GitHub Release：从 CHANGELOG 复制内容

## 文档维护清单

每次发版时检查：

| 文档 | 什么时候更新 |
|---|---|
| `CHANGELOG.md` | **每次发版必须** |
| `pyproject.toml` version | **每次发版必须** |
| `README.md` | 新功能/安装方式变化时 |
| `AGENTS.md` | 架构/约定/命令变化时 |
| `skills/gaotai/SKILL.md` | 创作方法论变化时 |
| `docs/*.md` | 设计决策变化时 |
| `CLAUDE.md` | 通常不动（只有 @AGENTS.md） |

## 问题反馈

用 GitHub Issues，选对应模板：
- 🐛 Bug Report：复现步骤 + 期望行为 + 实际行为
- 💡 Feature Request：场景 + 建议方案
- 📝 Documentation：哪里不清楚 / 缺什么

## License

MIT。贡献即表示你同意以 MIT 协议授权你的代码。