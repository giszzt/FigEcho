# Quality Rubric

抽取质量和成图质量分开验收。一个干净的 Prompt 不等于成图像；一张好看的图也不等于风格抽取得准。

## Extract Mode

### Evidence

- 每个锚点都有可观察事实和参考区域；
- 单图与多图置信度边界正确；
- 不把内容相关栏数、品牌元素或独特角色当成稳定风格。

### Specificity

- 至少五个锚点、四个维度、权重合计 100；
- 锚点写组合关系、比例、层级或重复规律；
- anti_generic 能指出最可能出现的模板化替代，并给正向目标。

### Portability

- style-prompt.md 不依赖本轮参考图语境；
- 不出现源专有词和源内容排除声明；
- 内容插槽明确，换主题后不需要重写风格主体；
- 布局明确按新内容拓扑重算，不固定源图的业务分区和栏数；
- 图标模块只规定画法，具体题材从新内容派生，不列举源图对象清单；
- 配色保留具体 #RRGGBB 色值，但强调色使用中性槽位并按新内容层级重新映射；
- Logo、照片、3D、渐变、发光、玻璃和阴影不作为跨任务绝对禁令；用户提供或内容必需的素材有明确条件入口；
- 默认中文提示词完整覆盖图像类型、内容结构、整体版式、组件、连接线、图标、配色、字体、视觉气质、关键风格特征和生成约束；
- 只读 Prompt 就能还原布局、组件、线条、配色、字体/图标和密度气质；
- prompt-only 的用户回答只包含完整提示词，不暴露内部规范和验证文件。

### Section completeness

- 每个模块达到 prompt-contract.md 的完整约束组，不存在只有标题或抽象形容词的模块；
- 【整体版式】有具体画布比例、阅读路径、网格、间距/留白和密度；
- 【组件语言】有形状、描边、填充和内边距；
- 【连接线】有线型、箭头、粗细、颜色和路由；
- 【插图与图标风格】有图标家族、轮廓、视角和细节等级；
- 【配色】至少包含三个不同的 #RRGGBB 色值，并映射到至少三个语义角色；
- 【字体层级】至少覆盖主标题、模块标题和正文，并说明字体类别与层级参数；
- 【关键风格特征】包含 5–7 条编号特征。

## Style Library Gates

- 只有用户明确要求保存时才持久化 Style Pack；
- Style Pack 同时包含 style-prompt.md、style-spec.json 和至少一张原始参考图；
- 原始参考图的复制件与哈希完整，绝对来源路径不进入 manifest；
- 风格指纹重复时不创建第二个 active 模板；
- candidate 可以被点名复用，但默认推荐优先 validated；
- validated 必须有通过门槛的 style-review；
- rendered validation 与 portability validation 分开：同题成图可以证明风格锚点可见，不能证明模板跨主题可迁移；
- portability_status = passed 必须有一张不同主题、不同对象或不同拓扑的新图，并通过布局重规划、图标题材派生、色彩语义重映射和无源内容残留四项检查；
- preview 只用于浏览，生成时仍绑定原始参考图；
- catalog、pack、Prompt、Style Spec 和参考图哈希全部通过 style_library.py validate。

## Generate Mode Hard Gates

### Render evidence

- render-check.json 存在，且 status 不为 fail；
- 实际画幅与 job-plan canvas.aspect_ratio 一致；拿到别的画幅时已重生成或已重做布局规划，没有拉伸和裁切；
- style-spec 的色值至少三项在成图中可测到；
- 分辨率足以让最小标签可读。

客观检查是证据，不是判断。它通过不等于风格通过，也不代替逐锚点看图评分。

### Content

- 所有 required 节点和关系存在；
- 文字、公式、数据和结论不被编造；
- 压缩没有改变因果、先后、范围和强弱。

### Planning

- 图型来自新内容关系，不是参考图栏数；
- visual-plan 的 zones、reading_path、focal_point 与视觉编码可见；
- 每个 primary 节点都有视觉角色；
- 每个 style anchor 有 placement 或 adaptation；
- 没有把原始长文直接塞进卡片。

### Prompt lineage and reference binding

- style-prompt.md 在生成前已经完成，并通过独立提示词检查；
- prompt.md 沿用同一十一模块结构，包含全部风格锚点与八个视觉维度的迁移规则，并填入 visual-plan 与 content-graph；
- 参考图通过 referenced_image_paths、num_last_images_to_include 或 reference_images_payload 真实进入生成调用；
- generation-record.json 记录 provider_mode、实际提示词、图片角色、绑定机制和输出文件；走第三方 API 时同时记录 provider.backend 与 provider.model；
- 最终回答同时交付实际使用的完整 prompt.md。

### Non-copying

- 不出现源图文字、Logo、数据、人物身份、水印或版权标记；
- 相似性来自可迁移视觉规则，不来自精确构图和专有内容。

硬门槛失败时不宣布完成。

## Raster Score

每项 0–4：

| 项目 | 0 | 2 | 4 |
|---|---|---|---|
| 内容 | 核心错误 | 次级遗漏 | 主节点与关系完整 |
| 文字 | 多处伪字 | 非关键错误 | required 文字准确可读 |
| 规划实现 | 机械堆卡片 | 部分落地 | 图型、分区、路径和层级一致 |
| 可读性 | 无法扫读 | 局部拥挤 | 目标尺寸清楚 |
| 风格锚点 | 只有表面色彩 | 命中 2–3 个维度 | 至少 4 个维度形成组合语法 |
| 非复制 | 带入专有内容 | 边界可疑 | 内容原创且无泄漏 |

风格锚点另做加权分：

weighted_score = sum(anchor_score / 4 × anchor_weight)

建议完成线：weighted_score ≥ 75，且至少四个不同维度得分不低于 3。该阈值是内部自评门槛，不是 provider-backed 风格相似度。

style-review.json 必须覆盖每个 signature anchor；每项包含 score、visible_evidence、mismatch 和 next_action。只写“整体符合参考风格”或“结构与信息密度符合”不构成证据。

## 迭代优先级

先处理会改变含义的硬错误；否则处理最高权重未命中的风格锚点；再处理可读性和局部装饰。每轮只改一项，并记录保持不变的规划与锚点。

## Evidence Boundary

- 自评只叫 self-review；
- 静态夹具只证明规则可回归；
- 未记录 provider、模型、命令和结果时不能称 provider-backed；
- 没有 reviewer、时间、先判断后揭晓和理由的比较不是盲评；
- 没有 OCR 或视觉相似度工具时写 missing evidence。
