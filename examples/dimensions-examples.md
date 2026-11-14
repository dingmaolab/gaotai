# 六维度组合示例

任何文章都是六个维度的组合。以下展示常见文体如何映射，以及未列出的文体如何自然落入已有维度。

## 用户提到的六类

| 文体 | source | urgency | audience | intent | format | 路径 |
|---|---|---|---|---|---|---|
| 人生感悟 | self | none | self | resonate | longform | full |
| 热点新闻 | event | hour | public | inform | short | flash |
| 人物传记 | material | none | public | record | longform | full |
| 开发实录 | hands_on | none | peer | teach | longform | fast/full |
| AI 新发布 | event | day | peer | inform | longform | fast |
| 行业观察 | mixed | none | peer | persuade | longform | full |

## 未列出但自然覆盖的文体

| 文体 | source | urgency | audience | intent | format |
|---|---|---|---|---|---|
| 书评影评 | material | none | public | persuade | longform |
| 工具推荐 | hands_on | day | beginner | teach | card |
| 带货文案 | hands_on | day | public | persuade | card |
| 诗歌散文 | self | none | self | resonate | short |
| 旅行游记 | self | none | public | record | longform |
| FAQ 答疑 | mixed | none | beginner | teach | short |
| 竞品分析 | material | day | peer | persuade | longform |
| 周报总结 | self | none | peer | record | short |
| 段子搞笑 | self | none | public | entertain | short |
| 直播话术 | mixed | hour | public | persuade | script |
| 产品 changelog | hands_on | day | peer | inform | short |
| 情感问答 | mixed | none | public | resonate | short |

**加新类型零代码改动。** 只需在对话中描述你的需求，Agent 自动判断维度组合。

## 维度取值速查

### source（素材来源）
- `self`：自身经历 → 无需外部核实，但不许编造
- `event`：外部事件 → 每个硬事实必须有 URL
- `material`：公开资料 → 引述标出处
- `hands_on`：动手实践 → 有命令/截图/输出
- `opinion`：纯观点 → 判断要有支撑
- `mixed`：混合 → 逐条按来源判定

### urgency（时效）
- `none`：无时效 → full 路径
- `day`：天级 → fast 路径
- `hour`：小时级 → flash 路径

### audience（读者）
- `peer`：同行 → 术语可用，语气直接
- `beginner`：小白 → 术语首次解释，语气耐心
- `public`：大众 → 少术语，语气 conversational
- `self`：自己 → 自由，私密

### intent（意图）
- `inform`：告知 → timeline / brief / data-first / listicle
- `persuade`：说服 → claim-evidence / contrast / qa
- `teach`：教会 → step-by-step / progressive-chain / demo
- `record`：记录 → timeline / scene-reflection / montage
- `entertain`：娱乐 → hook-punchline / listicle / story
- `resonate`：共鸣 → scene-feeling-judgment / letter / diary

### format（形态）
- `longform`：2000-6000 字，公众号文章
- `short`：300-1500 字，短文
- `card`：150-300 字，小红书卡片
- `imagepost`：180-250 字，公众号图文
- `script`：200-800 字，口播稿