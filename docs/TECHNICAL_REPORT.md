# 技术文档与演示复现

正式提交目录保存[技术文档PDF](../最终参赛提交材料/学脉XueMai-技术文档.pdf)和[有声演示视频](../最终参赛提交材料/学脉XueMai-演示视频-含旁白.mp4)。报告30页，视频477秒、1920×1080、30fps。图源、讲稿、连续录屏、声音、字幕与验证记录保存在工程中。

## 报告

入口为[main.tex](technical-report/main.tex)。图8与图18分别由[class-loop.tex](technical-report/figures/class-loop.tex)和[deployment.tex](technical-report/figures/deployment.tex)独立维护。图8从任务框下方引出直角通道，图18使用横平竖直的读写路径，并把“生成”标签放在本机边界外。

第五页把先修关系和教学材料说明放在课程主题表之前，正文继续自然衔接。正文保持宋体小四、英文Times New Roman、黑色文字、两字缩进与居中页码，现有完整界面图继续使用。

```powershell
.venv/Scripts/python.exe scripts/build_technical_report.py --reuse-assets
```

该命令直接编译现有图源和结果，沿用已提供的完整界面图，生成三遍交叉引用并渲染PDF。实验结果与统计图继续取自已完成实验。

## 视频

当前入口为[demo/current.json](demo/current.json)，源目录为[第十二轮演示源](demo/第十二轮演示源/)。开场右侧显示登录截图，教学情境的讲述沿用同一开场画面，然后展示更大的总体框架。框架位置和比例固定，先展示全貌，再依次高亮。

系统演示依次经过学生登录、学生10模块、教师登录、教师9模块，共294秒。教师登录从首页路径开始。后半段通过三个具体案例说明开发者提出要求、AI实现、发现问题、代码修改与验证结果，共126秒。原始记录、代码与测试结果随boards.json保留，展示文案和记录节选各自保存。

43段中文神经合成人声使用+7%基础语速，76条单行字幕与同次WordBoundary对齐。字幕透明，在实际内容下边界943像素至1080像素的中心呈现。结尾署名与感谢文字水平居中。

```powershell
.venv/Scripts/python.exe scripts/prepare_round11_video.py
.venv/Scripts/python.exe scripts/generate_demo_narration.py --round 12
.venv/Scripts/python.exe scripts/prepare_round11_video.py
.venv/Scripts/python.exe scripts/assemble_round12_video.py
.venv/Scripts/python.exe scripts/assemble_demo_audio.py
.venv/Scripts/python.exe scripts/audit_round12_media.py
.venv/Scripts/python.exe scripts/validate_submission.py
```

配音缓存按文稿、声音和参数区分。重建时使用随工程保存的连续素材，重新采集使用record-round12-modules.mjs与record-round12-materials.mjs，需准备带有既有官方会话11、12的隔离Mock演示库。新录制使用MediaRecorder控制页的单调时钟，在片段前后保留保护时间，剪辑器检查每段结束前仍处于当前画面。

无声中间片、SRT、ASS和验证JSON保存在视频工程目录。正式目录集中源码ZIP、README复现指南、AI协同开发记录、Git演进记录、PDF与唯一的有声MP4。完成中文提交后执行`scripts/prepare_submission.py`整理官方材料，源码取自当前Git提交；随后执行`scripts/validate_submission.py`检查媒体参数。后续按工程内的[协作约定](../AGENTS.md)维护。
