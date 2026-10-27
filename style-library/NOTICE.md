# 随包示例模板的来源说明

`templates/` 下的十个 Style Pack 是随包发布的示例，用来演示风格库的结构和检索方式，也可以直接拿来出图。

每个 pack 里的 `references/reference-01.png` 是抽取风格时用的原始参考图，属于第三方作品，仅作风格学习和模板演示之用，版权归各自作者，不在本项目的 MIT 许可范围内。`preview.png` 是基于这些参考图生成的示例成图，同样只作演示。

| 模板 | 参考图来源 |
|---|---|
| black-frame-serif-architecture | 网络流传的学术架构图，具体作者不详 |
| charcoal-dashed-node-explainer | ByteByteGo 的公开技术科普信息图，含其 logo |
| gray-column-layered-architecture | 网络流传的数据可视化平台分层架构图，含第三方产品名 |
| macaron-nested-method-figure | 某语音数据集论文的方法总览图 |
| playful-cartoon-schematic | 网络流传的卡通体方法示意图，具体作者不详 |
| research-proposal-roadmap | 一份公开的课题技术路线图 |
| research-proposal-roadmap-illustrated | 一份带图示的课题技术路线图 |
| blue-gray-pill-architecture-figure | 作者收集的架构图参考，具体出处未记录 |
| handdrawn-storyboard-roadmap | 作者收集的手绘分镜式路线图参考，具体出处未记录 |
| lavender-tonal-architecture-figure | 作者收集的淡紫色系架构图参考，具体出处未记录 |

如果你要二次分发这个包，或者对来源有顾虑，删掉 `templates/` 下对应目录即可，`style_library.py` 会在首次运行时自建空库，功能不受影响。原作者若认为不宜收录，请提 issue，会立即移除。

模板里的 `rights_scope` 一律标为 `personal-local`，含义就是这些资产不随包重新授权。
