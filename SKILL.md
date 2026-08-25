---
name: figecho
description: "Extract reusable visual systems from reference technical diagrams, architecture diagrams, scientific schematics, roadmaps, workflows, frameworks, and technical infographics. Create complete modular prompts, generate style-consistent PNG figures from new content, and save, search, name, validate, or reuse Style Packs with their original reference images. Use for 参考图风格抽取、技术图视觉语法、同风格技术图、技术路线图、架构图、科研示意图、方法框架图、风格模板库、保存或复用图片风格."
metadata:
  author: "giszzt / Jisai / 极思狂想"
  version: "0.1.0"
---

# FigEcho

从参考技术图中提炼可迁移的视觉系统，并将新的技术内容组织成同一视觉家族的图。

## 风格来源

任何任务在做风格判断之前，先确定这次的风格从哪里来。这一步必须发生在形成任何风格想法之前，一旦开始构想视觉语法就已经晚了。

- 用户点名模板时，从 [Style Library](references/style-library.md)精确解析 slug 或 name。
- 用户本轮给了参考图时，以参考图为风格来源。
- 用户既没给参考图也没点名模板时，先执行 `python scripts/style_library.py search "<图类型与内容关键词>"`，再执行一次 `list` 确认没有漏掉的候选，然后把命中结果按 name、适用场景和状态列给用户挑选，说明推荐哪一个以及理由。
- 检索确实没有可用模板时，向用户说明库里没有匹配风格，并询问是走原创新风格，还是由用户补一张参考图。得到明确答复前不进入原创风格。
- 用户明确说“不用库里的”“重新做一个风格”时，才走原创风格分支。此时 style-spec.json 的风格锚点来自主动设计而非参考图证据，必须在交付里说明这是原创风格，不声称与任何已有风格同族。

三个分支都要写进 job-plan.json 的 style_source：origin 取 reference-image、style-library 或 original；后两者必须记录 library_search.performed、实际用过的 queries 和命中的 candidates，以及引用用户答复的 user_confirmation；style-library 还要写 template_slug。validate_job.py 会硬校验这一节，缺了直接判失败。

原创分支的 reference_binding 保持 not-applicable/none/空图片，style-spec.json 的 references 为空、evidence_scope.generalization 写 original-style-no-reference，generation-record 的 binding_mechanism 写 none。不要用占位图假装绑定了参考图。

跳过检索直接自造风格属于流程失败，即使成图好看也不算通过。

## 交付判断

先根据用户真正要拿走的结果选择交付模式：

- 用户说“抽取风格”“给提示词”“复刻风格提示词”时，默认 prompt-only。
- 用户明确要风格分析、视觉规范、结构拆解或报告时，使用 analysis-and-prompt。
- 用户要求直接画图、生成图片或出图时，使用 image-and-prompt。
- 用户要求给风格命名、保存模板、查看风格库或复用已有风格时，按 [Style Library](references/style-library.md)执行。
- 用户只给内容、要求出图且没有参考图时，仍是 image-and-prompt，但风格必须先按上面的风格来源判定走完检索与确认。
- 用户同时给出参考图和新内容但没说要不要出图时，先问一句要提示词还是要成图，不默认调用图像模型。

无论是否成图，最终交付都包含完整提示词。内部分析文件用于保证质量，不自动变成用户交付物。

## Compact Workflow

1. 按上面的风格来源判定确定分支：点名模板就解析 Style Pack 并读取其 Prompt、Style Spec 和原始参考图；有参考图就查看参考图，区分风格不变量、内容适配规则和本次专有内容；两者都没有就先检索风格库并与用户确认，确认复用某个模板后回到模板分支，确认原创后进入原创风格分支。
2. 按 [视觉指纹](references/visual-grammar.md)创建 style-spec.json：提炼 5–7 个高辨识度风格锚点，覆盖至少四个视觉维度，并记录证据、权重、置信度和迁移规则。prompt_token 使用用户要求的提示词语言，默认中文。
3. 所有任务都先按 [提示词契约](references/prompt-contract.md)创建 style-prompt.md。它是唯一的风格约束源，默认采用完整的中文分模块结构，并确保脱离当前参考图语境仍可直接使用。
4. 成图任务按 [内容图谱](references/content-graph.md)整理用户材料，再按 [图示规划](references/visual-planning.md)创建 visual-plan.json，明确沟通目标、核心叙事、图型、布局、阅读路径、信息层级、视觉编码和内容压缩。
5. 成图任务以 style-prompt.md 为母版，将新内容和 visual-plan 填入同一分模块结构，形成 prompt.md。不得另写一份简化的散文式生成提示词。
6. 出图前锁定画幅：把 visual-plan 的画布比例写进 job-plan.json 的 canvas.aspect_ratio，后续所有检查都以它为准。
7. 按 [ImageGen 适配器](references/imagegen-adapter.md)选后端：当前 Agent 有内置图像工具就用它；没有就用 scripts/generate_figure.py 走第三方 API。把参考图作为真实图片输入，与 prompt.md 同时送入模型。
8. 出图后先用 scripts/check_render.py 测画幅、配色和密度，再查看图片逐锚点评分并定向修正。
9. 按 [质量标准](references/quality-rubric.md)完成检查。
10. 用户明确要求保存时，为 Style Pack 生成语义名称与 slug，保存 style-prompt.md、style-spec.json 和原始参考图；实际成图通过后晋级为 validated。

## 提示词标准

- 默认使用中文分模块结构，至少包含：图像类型、内容结构、整体版式、组件语言、连接线、插图与图标、配色、字体层级、视觉气质、关键风格特征和生成约束。
- 每个模块写成具体、可执行的制图指令；不能只拼接风格锚点或输出简短英文摘要。
- 通用风格提示词必须自包含，不依赖当前对话中的图片编号、代词或源图专有信息。
- 成图提示词沿用相同的十一模块结构，将内容槽位替换为已规划的新图内容；可在模块前标注参考图的输入角色，但不得增加“新图主题”模块。
- 成图提示词必须保留 style-prompt.md 的全部风格锚点和关键视觉规则，提示词的变化只服务于填入内容与落实图示规划。
- 固定内容改写为占位符；稳定视觉语法写成明确规则；受内容影响的栏数和节点数写成可适配范围。
- 通用模板只保存图标画法，不保存数据库、地图、人物、矿石等具体题材；图标题材必须从新内容的实体、对象和动作中派生。
- 配色保留具体 #RRGGBB 色值；背景、文字、描边等稳定角色可以固定，彩色强调使用 A/B/C 等中性槽位，并按新内容的层级与分组重新映射。
- 布局保留比例、节奏、对齐与容器语法，但主区数量、宽度和阅读路径必须按新内容拓扑重新规划。
- 内容准确、关系正确、不编造、不泄漏源内容、文字清晰和无裁切属于硬约束；Logo、照片、3D、渐变、发光、玻璃、阴影等属于参考图默认或本次条件，不得一刀切为跨任务禁令。
- 风格相似性必须来自布局、组件、线条、配色、字体或图标等多维组合，不能只来自配色。
- 【配色】必须把背景、结构、文字/线条、强调等语义角色映射到具体的 #RRGGBB 色值；至少给出三个不同色值，不能只写“浅黄、深蓝、低饱和”等泛称。
- 每个模块都要满足 [提示词契约](references/prompt-contract.md)规定的约束组，只有标题或抽象形容词的模块不算完成。

## 风格资产

- Style Pack 的视觉锚点使用原始参考图，不以合成样板或预览图替代。
- 模板 name 默认取 4–8 字的中文名，按「特征词 + 图类型」组合，特征词必须是该风格独有的可观察特征（如“马卡龙套盒方法图”）；禁止“科技风”“简约风”一类通用形容词和无信息编号，slug 用语义对应的英文短横线写法。保存前先把候选名说给用户确认。
- 入库必须同时写 aliases，覆盖用户可能的 4–6 种中文叫法；检索只认 catalog 的 name、slug、aliases、tags、best_for，文件夹名和提示词正文都不参与匹配。用户说出未收录的叫法时用 `rename --add-alias` 补进库。
- 用户点名某个风格却搜不到时，先确认当前 skill 安装读的是哪个 style-library，再判断是模板缺失还是别名缺失，不要直接凭记忆重建风格。
- 模板默认状态为 candidate；通过实际成图的逐锚点评分后才能成为 validated。
- rendered validation 与 portability validation 分开；只有完成不同主题迁移测试并通过四项适配检查后，portability_status 才能从 untested 变为 passed。
- 复用模板时，原始参考图与完整模板 Prompt 必须共同进入生成调用。
- 风格指纹相同的模板不重复入库；差异不足以形成新视觉家族时更新或归档已有模板。
- 只有用户明确要求保存时才持久化参考图。随包发布的是 style-library/templates 里的示例模板，用户新建的模板属于本地个人资产，不自动进入任何发布包。

## 用户呈现

prompt-only：

- 在最终回答中直接完整粘贴 style-prompt.md。
- 只给提示词，不附风格报告、JSON 规范、质量报告或内部文件列表。
- 除一句必要引导外，不在提示词前后增加分析说明。

analysis-and-prompt：

- 先给简洁风格结论，再给完整提示词。
- 只有用户需要下载或复用结构化规范时才提供相应文件。

image-and-prompt：

- 展示最终图片，并附本次实际送入模型的完整 prompt.md。
- 不默认展示内部规划、结构化规范或质量报告。

## 质量要求

- 风格锚点来自可观察证据，不能仅使用“科技感、专业、简洁”等泛化形容词。
- 无参考图任务必须留下风格库检索记录与用户确认记录；没有这两条就直接原创风格的，判为不通过。
- 原创风格分支里，style-spec.json 的 references 为空、style-review 缺少参考图比对，交付时如实说明这些证据缺口，不按复刻任务的口径声称风格一致。
- 图型和布局由新内容的关系与沟通目标共同决定，不机械照搬参考图的栏数。
- 每个主节点都有明确视觉角色，每条必要关系都有对应视觉编码。
- 最终图至少体现四个不同维度的风格锚点。
- "提示词中写了参考图"不等于模型收到参考图；生成前必须记录实际图片绑定机制和输入角色。
- 画幅在规划阶段锁定，出图后用 check_render.py 核对；拿到非计划画幅时重生成或重做布局规划，不拉伸也不裁切。
- 成图后逐个风格锚点记录可见证据、偏差和分数；没有逐项证据时不得声称风格相似度通过。
- 未完成 OCR、模型对比或人工盲评时，如实标记内部证据边界，但不把验证过程塞进 prompt-only 的用户回答。

## Output Contract

- prompt-only：完整提示词正文。
- analysis-and-prompt：简洁风格分析 + 完整提示词。
- image-and-prompt：最终 PNG + 完整提示词。

内部可使用 job-plan.json、style-spec.json、style-prompt.md、content-graph.json、visual-plan.json、generation-record.json、render-check.json、style-review.json 和 quality-report.md；它们不属于默认用户交付。成图任务中的 prompt.md 始终是用户交付物。

## 工具

    python scripts/init_job.py ./figecho-job --mode extract --delivery prompt-only --reference ./reference.png
    python scripts/init_job.py ./figecho-job --mode generate --delivery image-and-prompt --reference ./reference.png --title "New figure"
    python scripts/generate_figure.py --precheck
    python scripts/generate_figure.py --prompt-file ./figecho-job/prompt.md --reference ./reference.png --out ./figecho-job/output/final.png --record ./figecho-job/generation-record.json --aspect-ratio 16:9
    python scripts/check_render.py ./figecho-job/output/final.png --style-spec ./figecho-job/style-spec.json --expect-aspect 16:9 --report ./figecho-job/render-check.json
    python scripts/validate_job.py ./figecho-job --require-outputs
    python scripts/style_library.py add --job-dir ./figecho-job --name "马卡龙套盒方法图" --slug macaron-nested-method-figure --alias "马卡龙方法图" --alias "淡彩嵌套方法图"
    python scripts/style_library.py rename macaron-nested-method-figure --add-alias "奶油色方法图"
    python scripts/style_library.py search "马卡龙方法图"

权限、隐私和失败处理见 [运行边界](references/trust-boundary.md)。
