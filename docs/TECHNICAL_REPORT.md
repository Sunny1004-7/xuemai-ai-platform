# 技术文档与演示复现

正式报告为[技术文档PDF](deliverables/xuemai-technical-report.pdf)，可编辑入口为[main.tex](technical-report/main.tex)。报告30页，封面包括学校、专业、参赛学生和指导教师刘帅。摘要三段独立成页，正文使用两级标题、小四宋体、英文Times New Roman与黑色文字，段首两字，底部居中页码。八张应用图保留完整导航、课程栏与工作区，按100%版心宽度放置。

总框架沿用[统一母版](technical-report/figures/overall-framework.tex)。图4、图8和图18分别由[path-search.tex](technical-report/figures/path-search.tex)、[class-loop.tex](technical-report/figures/class-loop.tex)和[deployment.tex](technical-report/figures/deployment.tex)独立维护，采用方框与箭头表达学习规划、教学分层和部署关系。生成器保留这三份图源，其余图源继续按既有机制组织。实验入口、逐例结果和Token账本见[实验目录](experiments/round10/README.md)。

## 重建报告

准备XeLaTeX、宋体、Times New Roman和工具依赖，再安装 `scripts/requirements-experiments.txt`。审阅包将480张截图置于“界面截图”，重建时复制到下列截图目录并保留全部索引。

```powershell
.venv/Scripts/python.exe scripts/build_technical_report.py --screenshots 交付审阅包/界面截图_20261117_221559 --record docs/rounds/2026-11-17-第十一轮文档表达与模块化演示.md
```

构建器校验232份冻结实验文件的摘要，再读取事实表与回归结果，更新文字、核对截图覆盖和源码指纹，执行三遍编译并渲染全部页面。`--materials-only` 模式沿用已完成的统计图与实验结果。真实模型实验由独立命令显式执行。五项方法的定义、公式与逐例结果在本轮保持一致，新增文字解释各项设计如何进入学习活动、教师决策与反馈流程。

## 连续模块演示

[正式成片](deliverables/xuemai-demo-1080p.mp4)为475.5秒，1920×1080、30fps、H.264/AAC。问候与作品介绍之后进入教学情境，依次介绍学生10个模块、教师9个模块，系统界面共278秒。后半段统一使用“AI协同过程复现展示”标题，展示2026年11月3日和12日的真实Prompt、代码差异、问题修复与验证，合计130.5秒。作者在封面和结尾署名。

当前入口为[demo/current.json](demo/current.json)，源目录为[第十一轮演示源](demo/第十一轮演示源/)。工程保留完整连续WebM与MP4、模块操作及业务结果、历史开发原文、剪辑时间轴、26段配音、语音边界、77条字幕与69个验收关键帧。`scenes-source.json` 使用固定的场景标识关联讲稿、镜头和素材，当前讲稿、通用SRT与ASS由同一工程生成。

```powershell
.venv/Scripts/python.exe scripts/prepare_round11_video.py
.venv/Scripts/python.exe scripts/assemble_round11_video.py
.venv/Scripts/python.exe scripts/generate_demo_narration.py --round 11
.venv/Scripts/python.exe scripts/assemble_demo_audio.py
.venv/Scripts/python.exe scripts/audit_demo_audio.py
.venv/Scripts/python.exe scripts/audit_round11_media.py
.venv/Scripts/python.exe scripts/audit_round10_delivery.py
```

剪辑器优先读取本机最近一次录制，解压后的工程可直接使用随包交付的 `media` 连续素材。重新采集需先启动隔离Mock服务，随后运行 `node frontend/scripts/record-round11-modules.mjs`。画板重新采集使用 `node frontend/scripts/record-round11-materials.mjs`，完整操作见[模块与镜头](demo/第十一轮演示源/模块与镜头.md)。录制包含正常保存、发布和作答，已有两份官方响应从历史会话回看，本轮新增DeepSeek请求为0。

框架图先展示全貌4.943秒，随后移动五组高亮框，图像位置与比例固定。剪辑器比较原生视频和同状态完整视口截图，测得内容下边界为943像素，因此底部字幕中心为1011.5像素。ASS使用透明背景，最终成片逐条测量77条字幕的实际字形，最大居中误差为1像素。

整段配音缓存与WordBoundary已提供，重新合成需要语音服务网络。完整解码、音量、语段边界与本地Whisper回验均已完成，字符相似度0.9753，最大语速拟合倍率1.04416。具体记录见[视频验收](demo/验收结果.json)、[语音回验](demo/第十一轮语音转写回验.json)及[画面与字幕核验](rounds/第十一轮视频边界与字幕验收.json)。人工听审尚未进行。

交付一致性工具核对实验、PDF、视频、字幕及Token，按当前事实表生成[发布清单](deliverables/release-manifest.json)，与正式提交目录保留相同副本。
