# 风格学习分流示例

## 核心原则

**自己的文章更新 DNA，别人的文章只学技法。两者绝不混淆。**

## 场景一：喂自己的旧文

```bash
# 把你过去写的文章放进 exemplars
cp ~/my-old-posts/*.md style/exemplars/

# 学习 → 更新 L1 语言统计 + profile
python gaotai.py learn style/exemplars/post1.md style/exemplars/post2.md style/exemplars/post3.md

# 查看画像
python gaotai.py profile
# → confidence: low (3篇), avg_sentence_len: 25.6, pronoun_me_ratio: 0.81

# 生成风格卡
python gaotai.py card-build
```

**效果**：DNA 里的语言特征、人称占比、句长节奏都来自你自己的文字。

## 场景二：参考别人的文章

```bash
# 给一个相似账号的 URL
python gaotai.py learn --reference "https://mp.weixin.qq.com/s/xxx" --author "某作者"

# 或者直接贴正文
python gaotai.py learn --reference reference-text.md --author "某作者"
```

**效果**：
- 存入 `style/references/`，标记 `allowed_uses: [structure, data_discipline]`
- **不动 DNA**，不影响你的语言统计
- Agent 分析后填写三栏：他们怎么做 / 你可以借鉴什么 / 你不要做什么

**为什么分开**：如果把别人的文章混进 exemplars，你的「我」占比会被拉低（你 0.81 vs 他们 0.18），DNA 就失真了。

## 场景三：改稿后学习

```bash
# AI 写了初稿，你改成了终稿
python gaotai.py learn draft.md final.md
```

**效果**：
- 脚本做行级 diff，记录删了什么、加了什么
- Agent 分析差异意味着什么规则
- 写入 `style/lessons/`，初始 status=tentative
- ≥3 次出现 → suggest_confirm → 用户确认后才进风格卡

## 场景四：直接说偏好

在对话里说：
- "以后别用'赋能'这个词" → 立即 confirmed，加入 avoid
- "我喜欢短句" → tentative，多次确认后升为 confirmed
- "这篇开头太平了" → 记录 opening_type 偏好

**防漂移纪律**：
- 单次偏好 ≠ 固定风格
- 手动调整过的字段优先级最高
- 临时要求不自动成为长期规则

## 场景五：持续迭代

每次 `send` 成功后自动记录本篇的结构/开头/结尾/金句到 `style/recent.yaml`。

下次写稿前自动检查：
- 最近 2 篇同结构 → 强制换
- 金句重复率 >30% → 建议换新表达
- 最近 3 篇同开头类型 → 建议换

**不需要你额外操作，系统自己记住、自己检查。**