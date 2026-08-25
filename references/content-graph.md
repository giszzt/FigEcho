# Content Graph

content-graph.json 保存用户内容的语义结构，不替用户做版式。它只在 generate 模式必需。

## 节点

每个节点包含：

- id：稳定英文 ID；
- label：进入画面的短标签；
- source_text：对应的用户原文或可追溯摘要；
- role：hero、primary、secondary 或 annotation；
- details：可压缩但不能编造的说明；
- required：是否必须出现在图中。

主节点不是按原文段落机械切分。一个长段落可能包含“阶段、方法、输入、输出和指标”，应拆成不同语义角色；多个重复段落也可以汇成一个主节点加若干 supporting 信息。

## 分组

分组只表示用户内容真实存在的阶段、轨道、层级、系统边界或语义类别。不要为了套参考图的栏数创建虚假分组。

每个分组写：

- id、label、members；
- semantic_role；
- required。

## 关系

允许的 relation：

- sequence、branch、merge；
- contains、depends_on、maps_to；
- feedback、compares_with、annotates。

每条 required 关系必须引用现有节点或分组，并写清方向。装饰箭头不进入图谱。

## 文字

exact_text 保存必须逐字出现的标题、专名、数值、公式和短标签。长段落不应全部标为 exact；否则纯位图无法兼顾可读性与准确性。

同时记录：

- must_show：一定进入画面的信息；
- may_summarize：可压缩但含义不能变；
- may_omit_from_canvas：可留在配套说明中的细节；
- forbidden_inventions：不可由模型补写的阶段、指标、数据或结论。

## 从内容图谱到视觉规划

content-graph 回答“语义上有哪些对象和关系”，visual-plan 回答“怎样让人看懂”。禁止直接把节点数组等距排成几栏就调用生成。

进入 visual planning 前检查：

- 所有 primary 节点都在 reading_order；
- required relation 无悬空端点；
- exact_text 足够短；
- source_text 可追溯到用户材料；
- supporting 内容已经分成可压缩与不可遗漏两类；
- 没有从参考图借来原文不存在的阶段或关系。
