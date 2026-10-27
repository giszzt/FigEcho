# Changelog

本项目遵循 [Semantic Versioning](https://semver.org/)。

## 0.2.0 — 2026-10-27

- 新增可视风格画廊：`style_library.py gallery` 生成离线浏览页，按视觉家族排序，支持四维筛选、模糊搜索与三图并排比较；写库命令执行后自动重建，`validate` 检查页面是否过期。
- Style Library 引入「风格家族 → 表达变体」组织与 `organization` 字段，新增 `taxonomy`、`classify` 命令；search/list 支持按用途、关系图型、视觉家族、表达方式筛选，并返回按家族分组的 `groups`，旧字段保持兼容。
- 出图后端改走 ListenHub OpenAPI，GPT 型号链自动降级并记录切换原因，出图前预估积分，支持比例扩充到 10 种；`LISTENHUB_API_KEY` 为新变量名，旧的 `LABNANA_API_KEY` 仍可用。
- 新增 4 个示例 Style Pack：蓝灰胶囊架构图、手绘分镜路线图、薰衣草淡紫架构图、浅彩行带图示图（课题路线图的图示变体）。
- 既有 6 个模板补齐家族与分类信息，黑框衬线架构图的提示词与 Style Spec 修订。
- 单元测试增至 67 项，新增画廊与家族检索测试。

## 0.1.0 — 2026-08-25

FigEcho 的首次公开版本。

- 支持 prompt-only、analysis-and-prompt 与 image-and-prompt 三种交付模式。
- 建立视觉指纹、内容图谱、图示规划、统一提示词谱系与逐锚点验收流程。
- 支持 Agent 内置图像工具与多个脚本化图片后端。
- 提供 Style Library 的保存、检索、重命名、归档、晋级与跨主题迁移验证。
- 文本资产采用跨平台换行规范化哈希，避免 Git 在 Windows 与 Unix 间转换换行符时产生误报。
- 项目作者身份统一为 GitHub 账号 `giszzt`，并保留 Jisai / 极思狂想署名。
- 随包发布 6 个示例 Style Pack、49 项单元测试与触发/输出评估样例。
