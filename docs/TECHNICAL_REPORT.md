# 技术文档与演示复现

当前正式报告为[29页技术文档](deliverables/xuemai-technical-report.pdf)，系统版本0.6.0。可编辑LaTeX源为[main.tex](technical-report/main.tex)，包含12幅TikZ、10张应用图（8张完整应用、2张细节子图）与17条参考文献。正文与标题黑色，小四宋体、英文Times New Roman、段首两字、居中页码，二级目录一页。完整界面按100%版心宽度排版，局部子图另行标明。

报告围绕课程学习、个性化辅导与教学协作组织，解释五项方法、产品入口、架构、意图控制和实际开发链。保留同约束路径基线、分层扰动与教师编排验证，新增顺序术语回归和正常接口的新内容流程。作者信息由[统一事实配置](submission-facts.json)维护。

## 统一总框架与报告

[总框架可编辑母版](technical-report/figures/overall-framework.tex)通过同一脚本导出PDF、SVG、PNG，共用于报告、README与视频。

```powershell
.venv/Scripts/python.exe scripts/build_framework.py
.venv/Scripts/python.exe scripts/build_technical_report.py --screenshots 交付审阅包/界面截图_20261112_195005 --record docs/rounds/2026-11-12-第九轮视觉与材料精修.md
```

安装XeLaTeX、pdftocairo、宋体、Times New Roman及scripts/requirements-tools.txt中的工具依赖。审阅ZIP将本轮480张截图放在“界面截图”，重建时复制为上述完整截图目录，保留三份索引。工具验证覆盖、源码指纹、尺寸与摘要，三遍编译并渲染全部页面，校验页数、字体和文字颜色。报告中的实验表格从原始JSON生成，组合图来源及像素范围另存JSON。

## 连续教学演示

[正式成片](deliverables/xuemai-demo-1080p.mp4)为473.47秒，1920×1080、30fps、H.264/AAC。问候介绍、痛点、框架、界面、真实开发档案与总结依次展开。界面259.5秒，开发135秒，片长符合5—8分钟要求。

界面采用Chromium原生标签页媒体流采集，保留真实操作、流式回复、图谱和实验变化。教学过程共用课程、学生和任务，涵盖错误、路径、个人辅导、理解检查、班级证据、教师方案、审核发布、学生完成与教师反馈。复用两次已有官方Flash响应，本轮新增DeepSeek请求0次。新单元流程使用正常接口与Mock完成。

可编辑源位于[第九轮演示源](demo/第九轮演示源/)，包含连续MP4、原始WebM、事件、画板HTML、实际Git差异、剪辑时间轴、20个语段音轨、边界和72条语义单行字幕。既有真实教学和开发素材引用第七、八轮演示源/media，正式包一并收录。当前入口由demo/current.json明确指定。

```powershell
.venv/Scripts/python.exe scripts/assemble_round9_video.py
.venv/Scripts/python.exe scripts/generate_demo_narration.py --round 9
$env:XUEMAI_VIDEO_ROUND='9'
.venv/Scripts/python.exe scripts/assemble_demo_audio.py
.venv/Scripts/python.exe scripts/audit_demo_audio.py
```

剪辑可直接使用交付的media文件重建。云希中文神经合成人声按完整语段生成，缓存已提供，重新合成需要网络语音服务。底部字幕按同次WordBoundary换算，透明背景、轻描边。最大拟合倍率1.04965，语段无重叠，最大间隔6.816秒。完整解码、音量、43帧视觉检查和本地Whisper回验已完成，字符相似度0.9223。尚未人工听审，具体记录见[视频验收](demo/验收结果.json)和[语音回验](demo/第八轮语音转写回验.json)。

原生录制使用独立目录，在首块校验WebM签名，记录100%缩放和实际采集视口。连续教学录制工具在frontend/scripts下，作品与开发档案分别由record-round8-tour.mjs和record-round8-boards.mjs组织。采集使用专用服务与数据库，普通回归保持Mock。

七个框架分组由TikZ实际节点锚点导出，坐标见figures/xuemai-framework-regions.json。高亮计算包含图像等比缩放、居中留白与8像素外边距，字幕使用实际字体宽度测量。正文引用采用自动编号的可点击小号上标，代码框与正文的间距另有几何核验。
