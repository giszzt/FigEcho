# Visual Planning

用户的原始文字通常是内容材料，不是图示方案。生成模式必须先把“说了什么”转成“读者怎样看懂”，再调用图像模型。

visual-plan.json 记录可审查的设计决策，不记录冗长内部思维过程。

## 1. Communication Frame

先写清：

- audience：谁看；
- intended_use：论文、汇报、公众号、方案或教学；
- communication_goal：看完要理解什么；
- core_narrative：一句话串起全图；
- primary_takeaway：视觉重心应该落在哪；
- reading_time：快速扫读还是近距离精读。

内容完整不等于沟通有效。先确定读者要建立的心理模型。

## 2. Content Hierarchy

把 content-graph 分成：

- hero：全图核心结论或总机制，最多 1–2 个；
- primary：决定主结构的阶段、层级或系统；
- secondary：支撑 primary 的方法、能力或证据；
- annotation：指标、条件、说明和例子；
- omit_from_canvas：可留在配套文字、不进入画面的细节。

每项信息都要映射为一个视觉角色：标题、主区、卡片、标签、图标、连接线、图例或侧注。禁止把长段落原样塞进卡片。

## 3. Archetype Selection

根据新内容的真实关系选图型，而不是照搬参考图：

- sequence / roadmap：阶段推进；
- layered architecture：分层依赖；
- parallel tracks：并行流程或角色协同；
- matrix：两维交叉；
- hub-and-spoke：中心能力向外辐射；
- feedback loop：闭环迭代；
- nested system：包含与系统边界；
- comparison：方案对照；
- multi-panel：多个相对独立但共享语法的子问题；
- hybrid：主图型加一个次要关系层。

visual-plan 必须写 chosen_archetype、content_reason 和 rejected_alternatives。后者只需列 1–2 个最接近但不合适的方案及理由，防止默认套模板。

## 4. Layout Blueprint

用归一化关系描述：

- canvas 与 aspect_ratio：只能从目标后端支持的比例里选，第三方路线先跑 `generate_figure.py --precheck` 看模型比例表，别写 5:4、1.91:1 这类会被 400 拒掉的值；
- zones：每个主区的用途、相对面积、位置和内部层级；
- reading_path：读者从哪里进入、怎样推进、在哪里结束；
- focal_point：最大视觉权重；
- whitespace_strategy：哪些区域必须留白；
- density_budget：每区最多承载多少主节点、短标签和说明；
- connector_routes：主流程、反馈和跨区关系怎样避开文字；
- mobile_or_slide_readability：在目标尺寸上能否扫读。

不要在这里量源图像素坐标。目标是新图的布局蓝图。

## 5. Visual Encoding

建立 content-to-visual 映射：

- 形状表达阶段、角色、数据、能力还是风险；
- 颜色表达分区、状态、类别或强调；
- 线型表达顺序、反馈、依赖、映射或包含；
- 图标表达对象或动作，不替代精确技术含义；
- 字号、字重和位置表达信息优先级。

每个编码要有 semantic_role，避免颜色和箭头只做装饰。

## 6. Style Reconciliation

把 style-spec 分成两类：

- stable_style：容器语法、线条气质、色彩关系、字体层级、图标抽象度、表面质感；
- content_conditional：栏数、节点数量、具体流向、局部插图和标题长度。

逐个 signature anchor 写 placement：它在新图哪个区域或组件体现。若某锚点与内容拓扑冲突，写 adaptation，不要静默丢弃。

## 7. Compression Policy

每条原始内容决定：

- verbatim：标题、专名、关键阶段；
- concise_label：压缩为 2–8 个字或短语；
- annotation：移到侧注或图例；
- represented_by_icon：可以由图标辅助但仍保留文字；
- omitted_from_canvas：不进入图面，但质量报告说明。

压缩不得改写因果、先后、包含、条件、范围和强弱关系。模型不能自创阶段、指标、数据或结论。

## Planning Gate

以下字段缺一即不出图：

- communication_goal、core_narrative、chosen_archetype；
- 至少两个 zones 或一个中心区加外围结构；
- reading_path、focal_point、density_budget；
- 每个 primary 节点的 visual_role；
- 每个 required relation 的 connector encoding；
- 每个 signature anchor 的 placement 或 adaptation；
- compression decisions；
- plan_risks 与对应 mitigation。
