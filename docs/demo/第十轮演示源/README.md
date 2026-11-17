# 当前视频工程

入口为 `../current.json`，讲稿为 `scenes.json`，剪辑依据为 `edit-timeline.json`。成片保持1920×1080、30fps，约7分40秒。

`media/boards-*` 是本次原生连续录屏，包含封面、教学背景、实验结果、18段真实开发档案与结束页。开发原文及Git差异由 `boards.json` 保留，档案日期为2026年11月3日与12日。`media/framework-*` 记录基于真实节点边界的总览和局部放大。节点坐标来自统一TikZ母版，语义切换来自同次配音边界。

师生系统操作沿用第七、八轮已保存的连续素材，具体引用保存在剪辑时间轴。学生错误、辅导、理解检查、教师分析、方案、发布、学生完成与反馈持续使用同一组对象。界面中两次官方模型响应保留原记录。本次202次真实实验请求另见 `../../experiments/round10`，统一预算与逐例失败均保留。

`audio/` 保存21段中文神经合成配音、WordBoundary、缓存摘要、分段索引及合成音轨。当前字幕为 `subtitles.srt` 与 `subtitles.ass`，通用副本同步更新，透明背景。`验收关键帧/` 保存逐场景、高亮和开发档案关键帧。当前媒体检查记录位于上级目录，人工听审尚未进行。

重建使用 `scripts/assemble_round10_video.py`、`generate_demo_narration.py --round 10` 和 `assemble_demo_audio.py`。随包交付的素材可直接重剪，重新录制使用 `frontend/scripts/record-round10-materials.mjs`。
