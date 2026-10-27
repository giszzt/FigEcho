# Creation Handoff — FigEcho 0.2.0

## Reference skills studied

- OpenAI bundled imagegen：参考图分角色送入与定向修改的做法，FigEcho 的 image-and-prompt 流程沿用。
- OpenClaw diagram-maker：节点、分组、关系先结构化再画，FigEcho 把它拆成 content-graph 与 visual-plan 两步。

## Candidate-specific lessons

- imagegen 的教训是参考图必须真正进入生成调用，预览图代替不了原图，FigEcho 因此规定复用时原始参考图与完整 Prompt 一起提交，画廊也只展示原始参考图。
- diagram-maker 的结构化思路适合新内容，不适合拿来抄源图拓扑，FigEcho 因此要求新内容重新规划布局。

## Deliberate rejections

- 不在运行时拼接父子提示词：家族只是组织与检索单位，每个变体保存完整 Prompt 和自己的参考图。
- 画廊不展示 validated、评分等维护状态，只服务挑风格，维护信息留给 `show` / `validate`。
- 个人参考图与画廊产物不进发布包，本次发布排除了一个个人模板。

## Original contributions

| 亮点 | 标注 |
|---|---|
| 写库命令自动重建离线画廊，`validate` 用 catalog 指纹查过期 | validated advantage（67 项单元测试含画廊测试） |
| 用途 / 关系图型 / 家族 / 表达四维交叉检索，结果按家族分组 | validated advantage（family search 测试） |
| GPT 型号链只在通道关闭时降级，并记录切换原因 | design advantage（本机实测可用，无自动化回归） |
| 跨主题迁移验证与成图验证分离 | design advantage |

## Evidence

- 触发评估：36/36 通过，见 `reports/trigger-eval.json`。
- 单元测试：67 passed。
- 输出质量、用户满意度、采用情况：missing evidence。
