# ImageGen Adapter

FigEcho 的成图路线只有位图。参考图用于条件化新图生成，不是修改对象。

模型后端可以是 Agent 内置图像工具，也可以是第三方图像 API。两条路线共用同一份 prompt.md、同一套输入角色和同一套验收标准，只有调用机制和记录字段不同。

## 前置门槛

调用前必须同时存在并通过验证：

- style-spec.json；
- style-prompt.md；
- content-graph.json；
- visual-plan.json；
- job-plan.json 的 mode = generate；
- job-plan.json 的 canvas.aspect_ratio 已锁定为具体比例，不是 TODO；
- prompt.md。

若 visual-plan 还没有选图型、布局蓝图、内容压缩和风格锚点落位，不得直接把用户长文与参考图一起送入模型。

## 后端选择

按顺序取第一条可用且成功的路线。**先盘点自己的工具**：当前 Agent 有接受参考图的内置图像生成能力时，那就是路线 1。

1. **内置图像工具**（Codex `image_gen`、自带图像 MCP 等）。参数表里没有参考图或输出路径选项不构成跳过理由，内置工具通过多模态上下文接收参考图。
2. **`scripts/generate_figure.py`**（第三方 API 适配器）。当前环境没有内置图像工具，或内置工具调用失败时使用。它自身的后端顺序是 Labnana GPT-Image-2 → Labnana Nano Banana → OpenAI 官方 → Gemini 官方 → 自定义命令。
3. 用户明确点名的其他后端。

判断"在不在 Codex"靠的是自己有没有内置图像工具，不是环境变量。Claude Code、Cursor 等没有内置图像工具的 Agent 直接走路线 2，不需要征求用户同意选后端；只有在没有任何后端可用、用户要求控制后端、或选择实质影响成本与质量时才问。

`python scripts/generate_figure.py --precheck` 报告脚本侧可用后端。precheck 为正不等于可以跳过内置工具。

密钥来自 `.env`：优先 skill 根目录 `.env`，其次 `~/.claude/image-backends.env`，最后复用 `~/.claude/skills/figedit-v2/.env`。复制 `env.example` 填 `LISTENHUB_API_KEY` 即可（旧名 `LABNANA_API_KEY` 仍认，同一把 lh_ 密钥）。不要求用户在对话里粘贴完整密钥。

## 输入角色

- 初次生成：每张用户参考图标为 style reference；
- 用户另外提供 Logo、照片或必须插入的素材时标为 supporting insert；
- 初次生成没有 edit target；
- 只有修正已生成草稿时，草稿才变成 edit target。
- 复用 Style Pack 时，pack references 目录中的原始参考图全部标为 style reference；preview 仅用于模板浏览，不作为默认生成输入。

参考图必须作为真实图片输入绑定到生成调用。只在 prompt.md 中写"参考图"或"Image 1"不算完成绑定。

supporting insert 不是 style reference。它只提供必须出现的内容资产，不决定整图风格；prompt.md 要说明保留内容真实性，并用模板的边框、裁切、色调、尺度和层级规则完成视觉整合。不得因为通用模板的默认平面风格而擅自删除用户要求的 Logo、照片或外部插图。

## 绑定机制

内置工具两类：

- 参考图有本地路径时，先查看图片，再在调用中使用 referenced_image_paths；
- 参考图只有会话附件身份时，使用最小充分的 num_last_images_to_include，把对应会话图片纳入调用。

第三方 API 一类：

- `reference_images_payload`。每张图按角色作为 `--reference PATH::ROLE` 传入，脚本把图片内联进请求体。角色缺省为 style_reference。

job-plan.json 的 reference_binding 必须记录 bound 状态、实际机制、图片角色和来源。调用结束后在 generation-record.json 中记录 provider_mode、实际 prompt 文件、图片绑定机制、输入图片与最终输出；provider_mode = external-image-api 时同时记录 provider.backend 和 provider.model。没有 bound 记录时不得生成，也不得把提示词中的角色声明当作调用证据。

使用命名模板时，先运行 style_library.py show 解析 Prompt、Style Spec 和原始参考图的绝对路径。查看原始参考图后再绑定；除非用户明确要求混合风格，不自动加入本轮其他参考图。

## 第三方调用

    python scripts/generate_figure.py \
      --prompt-file ./figecho-job/prompt.md \
      --reference ./reference.png \
      --reference ./client-logo.png::supporting_insert \
      --out ./figecho-job/output/final.png \
      --record ./figecho-job/generation-record.json \
      --aspect-ratio 16:9 --image-size 2K

prompt.md 原文提交，不另写一份英文摘要，也不为了迁就后端删掉风格锚点。提示词过长时先压缩【内容结构】里的说明文字，不压缩风格模块。

脚本行为：Labnana 把参数错误、额度不足和限流全部塞进 HTTP 400，靠状态码分不出来，所以按响应体里的 code 分流。29998（限流）按 20 秒起步的退避重试到 --max-retries 次，5xx 和连接中断也重试；29003（参数错误）不重试；21007（密钥无效）和 26004（积分不足）判为账号级失败，同一把密钥后面的 Labnana 模型直接跳过，不再白试一遍。每次尝试的 http_status、code 和 message 都写进 provider.attempts，比例改写和降级理由写进 provider.notes。

## 画幅

技术图的布局是按画幅规划的，画幅错了整张图的阅读路径都会塌。

**规划阶段就要选后端支持的比例。** `labnana-*` 路由走 ListenHub OpenAPI（`https://api.marswave.ai/openapi`，与 Labnana 同账号同密钥），表外比例一律 400：

- GPT 路由（型号链 `gpt-image-2` → `gpt-image-2.5-flare` → `gpt-image-2-official`）：`1:1` `2:3` `3:2` `3:4` `4:3` `4:5` `5:4` `9:16` `16:9` `21:9`，参考图最多 4 张；不支持的比例报 26019；
- `gemini-3-pro-image`：同上 10 种，参考图最多 14 张；不支持的比例报 29003。

GPT 型号链只在上游返回 "Model X is not available"（通道临时关闭）时才切下一个，切换写进 `provider.skipped_models` 和 `notes`。`gpt-image-2-official` 按 token 计价，同一张图约是 lite 档的两倍。每次出图前脚本先调免费的 estimate-credits，结果记在 `provider.estimate`。

脚本对表外比例不再直接丢参数，而是按对数距离吸附到最近的合法比例（`5:4` → `4:3`，`1.91:1` → `16:9`），
并在 `aspect_source` 记 `snapped`、在 `notes` 里写清楚。吸附结果和原计划差得远时，重做分区再出图，别硬套。

只有真被拒（29003）且模型本身支持省略比例时，才退到"不传 aspectRatio + 把比例写进提示词"这一步，此时 `aspect_source` 记 `prompt-only`。
这条路只对 `gpt-image-2` 开放：它在缺省时按提示词自选比例。`gemini-3-pro-image` 缺省时用的是 1:1 默认值，不是提示词，
省略参数只会静默换来方图，所以脚本宁可报错也不省。

`prompt-only` 是概率约束不是硬约束，提示词写了 16:9 也可能返回方图，必须用 check_render.py 复核实际画幅。

拿到非计划画幅的图时，按这个顺序处理：

1. 换一个能接受该比例的后端重生成；
2. 都不行时，按实际可得画幅重做 visual-plan 的分区与阅读路径，再重新出图；
3. 不要拉伸，不要裁切。裁切技术图会切掉标签和容器，拉伸会破坏字形和线宽比例。

## 查看与评分

生成后先跑客观检查，再做人工评分。两步都要做，顺序不能反：客观检查负责给证据，人工评分负责给判断。

### Render check

    python scripts/check_render.py ./figecho-job/output/final.png \
      --style-spec ./figecho-job/style-spec.json \
      --expect-aspect 16:9 \
      --report ./figecho-job/render-check.json

它测量画幅与计划是否一致、分辨率是否够用、style-spec 的色值有多少真的出现在图上及各自面积、背景占比与边缘密度是否落在合理区间、画布外圈是否有被裁切的墨迹。status = fail 时不得交付。

它测不了内容正确性、文字准确性、图型落地和源内容泄漏，这些仍由下面三项人工检查负责。不要用 render-check 的绿灯代替看图。

### Semantic check

- primary 节点是否存在；
- required relations 的方向与类型是否正确；
- exact text 是否可读、无错字；
- 是否新增了用户未提供的模块、数据或结论。

### Planning check

- chosen_archetype 是否真正可见；
- zones、reading_path、focal_point 和 density budget 是否落地；
- content-to-visual 映射是否一致；
- 该压缩的 supporting 信息是否仍挤占画面。

### Style check

创建 style-review.json，逐个 signature anchor 评分 0–4，并为每项记录 generated image 中的可见证据、偏差和下一步动作；按权重计算总分，同时检查是否至少覆盖四个不同维度。只像配色、其他维度均模板化时不算通过。render-check 的 palette 数据可以作为配色锚点的证据，其他维度仍需看图取证。

## 定向迭代

每轮只处理一个最高影响问题：

1. 选择内容硬错误、规划偏差或最高权重未命中的风格锚点；
2. 将当前草稿作为 edit target；
3. 同时保留原参考图作为 style reference，明确 change only X，重复需要保持的节点、关系、布局和其他锚点；
4. 重新查看并重跑客观检查与三类人工检查；
5. 不用整段新 Prompt 重开一张图来修一个局部错误。

第三方后端下同样成立：把上一版草稿以 `--reference draft.png::edit_target` 与原参考图一起传入，prompt 写 change only。后端不支持局部编辑时，保持同一份 prompt 只改动对应模块重生成，并接受构图会整体变化，在记录中写明这是重生成不是定点修改。

若局部编辑引入更大漂移，退回上一张通过更多门槛的版本，再用更小范围的修改。

## 保存

内置 imagegen 默认输出可能在 CODEX_HOME。项目交付必须把最终选择的 PNG 复制到任务目录 output/final.png；不覆盖用户源图，必要时使用版本号。第三方路线用 `--out` 直接落到 output/final.png。

## 失败处理

区分瞬时故障与参数故障。同一后端连续失败视为不可用，此时才下沉到下一后端并记录原因。没有任何后端可用时，交付已完成的 prompt.md 与全部规划，明确说明 PNG 未生成，不要静默降级成"给了提示词就算完成"。
