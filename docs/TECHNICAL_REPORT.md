# 技术文档与演示复现

正式报告为[技术文档PDF](deliverables/xuemai-technical-report.pdf)，可编辑入口为[main.tex](technical-report/main.tex)。封面保留学校、专业和作者，摘要三段独立成页，正文仅使用两级标题。小四宋体、英文Times New Roman、黑色正文和标题，段首两字，底部居中页码。八张应用图均保留完整导航、课程栏与工作区，按100%版心宽度放置。

总框架沿用[统一母版](technical-report/figures/overall-framework.tex)。其余图形按机制改为事件曲线、先修网络与活动序列、辅导时序、约束矩阵、错因热图、复习日历和对象关联，统计图从逐例结果生成。当前实验入口、任务、原始结果和Token账本见[实验目录](experiments/round10/README.md)。

## 重建报告

准备XeLaTeX、宋体、Times New Roman和工具依赖，再安装 `scripts/requirements-experiments.txt`。审阅包将480张截图置于“界面截图”，重建时复制至下列截图目录并保留全部索引。

```powershell
.venv/Scripts/python.exe scripts/build_technical_report.py --screenshots 交付审阅包/界面截图_20261117_173816 --record docs/rounds/2026-11-17-第十轮实验与参赛材料重编.md
```

构建器读取当前实验清单和回归结果，生成摘要数字、方法图、统计图与验证汇总，验证截图覆盖和源码指纹，执行三遍编译并渲染全部页面。实验数据在构建时直接读取，真实模型实验需另行显式执行。

## 连续教学演示

[正式成片](deliverables/xuemai-demo-1080p.mp4)约460.47秒，1920×1080、30fps、H.264/AAC。问候后交代教学背景，再引出学脉。师生连续界面约247.5秒，三条开发档案回放135秒。作者在封面和结尾署名。字幕采用透明背景与轻描边，21个完整语段由同次WordBoundary对齐到70条单行字幕。

当前入口为[demo/current.json](demo/current.json)，源目录为[第十轮演示源](demo/第十轮演示源/)。工程包含画板HTML、原始连续WebM与MP4、教学素材引用、实际Git差异、剪辑时间轴、音轨、语音边界、字幕和验收帧。界面继续使用此前已取得的真实师生会话，实验用量单列于本轮账本。

```powershell
.venv/Scripts/python.exe scripts/assemble_round10_video.py
.venv/Scripts/python.exe scripts/generate_demo_narration.py --round 10
.venv/Scripts/python.exe scripts/assemble_demo_audio.py
.venv/Scripts/python.exe scripts/audit_demo_audio.py
.venv/Scripts/python.exe scripts/audit_round10_media.py
```

剪辑器优先使用已交付连续素材。重新采集画板时启动docs静态服务至8010，再运行 `node frontend/scripts/record-round10-materials.mjs`。可选 `--framework-only` 补录框架。实际节点边界决定高亮与放大位置，语音边界决定切换时间。整段配音缓存已提供，重新合成需要语音服务网络。

音轨完整解码和本地Whisper回验已完成，具体媒体参数见[验收结果](demo/验收结果.json)，转写见[语音回验](demo/第十轮语音转写回验.json)。人工听审尚未进行。
