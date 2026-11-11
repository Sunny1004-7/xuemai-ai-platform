# 技术文档与材料复现

当前正式报告为[学脉XueMai技术文档](deliverables/xuemai-technical-report.pdf)，版本0.5，共30页。可编辑源为[main.tex](technical-report/main.tex)，十幅TikZ图源保存在同目录figures中，参考文献16条。本文是仓库内的材料导读；参赛正文以PDF为准。

报告从课程学习与日常教学的具体问题出发，介绍共享课程对象、圆环知识图谱、K-TRACE相关性修正证据、PATH-G约束路径、DIA-GUIDE协作编排、CLASS-LOOP动态分组、间隔复习、结构化辅导、资源增量检索，以及教师任务前后对照。连续作答计算示例直接使用平台计算函数生成，说明同一知识点在不同证据下的变化。开发意图、上下文组织与架构约束在“开发意图控制与可复现性”章集中说明。

文档有封面、目录、摘要和参考文献。正文为小四宋体，英文Times New Roman，段首两字缩进，文字统一黑色，页脚仅保留居中页码。公式采用标准数学字体，图片与TikZ保留正常配色；13张界面截图以版心100%宽度插入，不设高度缩放。447张原始界面截图随本轮审阅包提供。本轮补充双课程内容覆盖、真实目标预算、计划事件回写、Python实验与七类学情视图，更新固定种子合成案例的对照与消融结果。图色用于区别模块、教师确认及方法与对照。

## 重建报告

安装XeLaTeX及宋体、Times New Roman，并在应用依赖之外安装可选工具：

```powershell
.venv/Scripts/python.exe -m pip install -r scripts/requirements-tools.txt
.venv/Scripts/python.exe scripts/build_technical_report.py --screenshots 交付审阅包/界面截图_年月日_时分秒 --record docs/rounds/本轮记录.md
```

工具校验截图与当前源码一致，读取本轮已完成的后端和浏览器测试结果，生成计算示例并编译三次，核对不超过30页、文字全黑和字体，渲染所有页面供复核。编译中间文件保存在忽略目录，正式源文件不混入日志。执行前应完成对应轮次的测试并使用实际截图目录。

## 演示视频

[正式演示](deliverables/xuemai-demo-1080p.mp4)时长7分30秒，1920×1080，H.264/AAC，含晓晓中文神经合成语音与底部字幕。前4分40秒展示学生与教师操作，随后120秒回放三组已经发生的开发协作，再用40秒说明四项方法及PATH-G、CLASS-LOOP实验，最后10秒为片尾。开发原话来自2026年11月3日可见记录节选，与当前方法介绍区分标识。

分镜与讲解稿见[演示分镜](demo/讲解稿与分镜.md)，验收数据见[视频验收结果](demo/验收结果.json)。录制脚本在独立数据库和隔离端口上执行Mock业务，不消耗DeepSeek额度。`build_demo_round5.py`生成回放页，`record-demo.mjs`执行双课程浏览器录制，`generate_demo_narration.py`通过网络语音服务逐句生成配音，字幕读取同次TTS的WordBoundary并按速度调整，`assemble_demo_audio.py`合成正式视频。本轮包含55句配音和71条字幕，正式成片已抽查28个时间点。素材重建需要`scripts/media-requirements.txt`中的可选依赖；配音服务需要网络，缓存按文案、声音、语速和边界方式摘要匹配。

系统验证、材料生成和开发记录分别保存，正式PDF不包含本机绝对路径、内部任务文件或修改交接信息。
