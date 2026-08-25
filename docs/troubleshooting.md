# FigEcho 排错手册

README 负责说明 FigEcho 的主路径；这里集中记录安装、提示词、出图与 Style Library 的故障定位方法。

## 安装与后端

| 现象 | 原因 | 处理 |
|---|---|---|
| `generate_figure.py` 返回 `unavailable` | 没有配置任何第三方后端密钥 | 复制 `env.example` 为 `.env` 并填写可用密钥，或确认当前 Agent 自带可接收参考图的图像工具 |
| 后端返回 HTTP 400 | Labnana 会把参数、限流、密钥与额度问题统一放在 400 响应中 | 查看 `generation-record.json` 的 `provider.attempts`：29003 为参数错误，29998 为限流，21007 为密钥无效，26004 为积分不足 |
| 比例参数被拒 | 请求比例不在当前模型支持列表中 | 生成前运行 `python scripts/generate_figure.py --precheck`；脚本会吸附到最近合法比例并记录 `aspect_source=snapped` |
| 规划为 16:9，结果却是方图 | 后端忽略或固定了输出比例 | 更换后端重生成；若所有后端都只能给方图，应按实际画幅重做 `visual-plan.json`，不要拉伸或裁切 |

## 提示词与成图

| 现象 | 原因 | 处理 |
|---|---|---|
| 提示词只有配色描述 | 风格锚点缺少布局、组件、字体或图标维度 | 重新检查 `style-spec.json` 的维度覆盖、证据与权重 |
| 配色没有具体编码 | Prompt 只有色彩形容词 | 为背景、结构、文字/线条与强调角色提供至少三个 `#RRGGBB` 色值 |
| 只要提示词却收到多个内部文件 | 交付模式没有按用户意图收敛 | 使用 `prompt-only`，最终只粘贴完整提示词 |
| 新图退化为通用卡片模板 | 图示规划没有落实高权重风格锚点 | 检查每个锚点是否在 `visual-plan.json` 中有明确落位 |
| 提示词写了参考图，但成图不像 | 参考图没有作为真实图片输入送进模型 | 检查 `reference_binding` 与 `generation-record.json` 的绑定机制 |
| 成图提示词变成简短英文摘要 | 生成路线绕开了统一提示词母版 | 以 `style-prompt.md` 为母版重新编译十一模块 `prompt.md` |
| 原始文字全部挤进画面 | 内容没有区分主节点、短标签与说明 | 调整内容压缩策略、每区信息预算与文字层级 |
| 中文标签错误或关系遗漏 | 单次生成承载的信息过多 | 缩短标签，并针对一个文字区或一组关系定向修正 |
| `render-check` 报配色未命中 | 强调色没有实际出现，或 Style Spec 色值不准 | 先查看图片，再决定修 Prompt 的配色模块还是修 Style Spec |

## 风格来源与 Style Library

| 现象 | 原因 | 处理 |
|---|---|---|
| 没给参考图却直接生成了新风格 | 跳过了风格来源判定 | 先执行 `style_library.py search` 与 `list`；没有匹配项时再让用户选择原创或补参考图 |
| `validate_job` 报缺少 `style_source` | 成图任务没有记录风格来源 | 在 `job-plan.json` 写入 `style_source.origin`；库检索或原创分支还需记录查询、候选与用户确认 |
| 库里有相近风格却没有命中 | name、slug、aliases、tags、best_for 没覆盖用户叫法 | 用 `rename --add-alias` 补充准确别名 |
| 模板无法入库 | Prompt、Style Spec、原始参考图或具体色值缺失 | 先通过任务校验，再执行 `style_library.py add` |
| 模板重复 | 新 Style Spec 与已有 active 模板的视觉指纹一致 | 复用已有模板，或归档旧模板后再处理 |
| 模板复用后风格漂移 | 只用了 Prompt 或 preview | 使用 `style_library.py show` 返回的原始参考图路径，并与完整 Prompt 一起送入模型 |
| 换题后仍出现旧图标或旧业务色义 | 把源内容实例写进了通用规则 | 图标只保留画法；强调色使用中性槽位，并按新内容重新派生与映射 |

## 推荐检查顺序

1. 运行 `python scripts/generate_figure.py --precheck` 确认后端与比例。
2. 运行 `python scripts/validate_job.py <job-dir> --require-outputs` 检查任务文件。
3. 查看 `generation-record.json` 确认实际 Prompt、模型与参考图绑定。
4. 查看 `render-check.json` 确认画幅、配色与裁切风险。
5. 最后查看图片，核对文字、关系、图型与每个风格锚点的可见证据。
