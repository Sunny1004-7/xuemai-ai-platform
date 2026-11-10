# 技术文档与材料复现

当前正式报告为[学脉XueMai技术文档](deliverables/xuemai-technical-report.pdf)，版本0.2，共30页。可编辑源为[main.tex](technical-report/main.tex)，八幅TikZ图源保存在同目录figures中。本文是仓库内的材料导读；参赛正文以PDF为准。

报告从课程学习与日常教学的具体问题出发，介绍共享课程对象、圆环知识图谱、时间折减Beta证据、提示与重复作答权重、先修学习路径、间隔复习、结构化辅导、资源增量检索，以及教师任务前后对照。连续作答计算示例直接使用平台计算函数生成，说明同一知识点在不同证据下的变化。开发意图、上下文组织与架构约束在“核心计算与业务执行”章集中说明。

文档有封面、目录、摘要和参考文献。正文为小四宋体，英文Times New Roman，段首两字缩进，文字统一黑色，页脚仅保留居中页码。公式采用标准数学字体，界面截图转灰度，保留原色的336张截图随本轮审阅包提供。

## 重建报告

安装XeLaTeX及宋体、Times New Roman，并在应用依赖之外安装可选工具：

```powershell
.venv/Scripts/python.exe -m pip install -r scripts/requirements-tools.txt
.venv/Scripts/python.exe scripts/build_technical_report.py --screenshots 交付审阅包/界面截图_年月日_时分秒 --record docs/rounds/本轮记录.md
```

工具校验截图与当前源码一致，读取本轮已完成的后端和浏览器测试结果，生成计算示例并编译三次，核对不超过30页、文字全黑和字体，渲染所有页面供复核。编译中间文件保存在忽略目录，正式源文件不混入日志。执行前应完成对应轮次的测试并使用实际截图目录。

## 演示视频

[正式演示](deliverables/xuemai-demo-1080p.mp4)时长7分钟，1920×1080，H.264/AAC，含晓晓中文神经合成语音与底部字幕。前4分40秒展示学生与教师操作，随后130秒回放已经发生的开发协作，最后10秒为片尾。开发原话来自2026年11月3日可见记录节选，与当前方法介绍区分标识。

分镜与讲解稿见[演示分镜](demo/讲解稿与分镜.md)，验收数据见[视频验收结果](demo/验收结果.json)。录制脚本在独立数据库和隔离端口上执行Mock业务，不消耗DeepSeek额度。`build_demo_evidence.py`生成回放页，`record-demo.mjs`执行浏览器录制，`generate_demo_narration.py`通过网络语音服务逐句生成配音和字幕，`assemble_demo_audio.py`合成正式视频。素材重建需要`scripts/media-requirements.txt`中的可选依赖；配音服务需要网络，已有音频缓存可复用。

系统验证、材料生成和开发记录分别保存，正式PDF不包含本机绝对路径、内部任务文件或修改交接信息。
