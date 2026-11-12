# 技术文档与演示复现

当前正式报告为[29页技术文档](deliverables/xuemai-technical-report.pdf)，系统版本0.6。可编辑LaTeX源为[main.tex](technical-report/main.tex)，包含13幅TikZ、10张完整应用截图与17条参考文献。正文与标题为黑色，小四宋体、英文Times New Roman、段首两字缩进、居中页码，二级目录一页。截图以100%版心宽度保留导航、顶部栏与工作区。

报告说明五项方法的输入、输出、机制与产品入口，补充同约束可行贪心基线、分层鲁棒性、师生教学流程及三条真实开发链。实验和官方请求分别记录，原始输入与逐例结果可核对。

## 重建报告

安装XeLaTeX、宋体、Times New Roman，以及scripts/requirements-tools.txt中的可选依赖后，使用本次完整截图目录执行命令。

```powershell
.venv/Scripts/python.exe scripts/build_technical_report.py --screenshots 交付审阅包/界面截图_20261112_145705 --record docs/rounds/2026-11-12-第七轮技术论证与连续教学演示.md
```

原工程中的截图目录为“交付审阅包/界面截图_20261112_145705”。审阅ZIP将图片放在“界面截图”；重建报告时先创建“交付审阅包”，把完整截图目录复制到命令所用位置。工具验证源码指纹、覆盖、尺寸和摘要，从公开回归记录生成统计，编译三次并渲染全部页面，校验页数、字体与文字颜色。实验表格直接读取原始JSON。

## 连续教学演示

[正式演示](deliverables/xuemai-demo-1080p.mp4)约6分34秒，1920×1080、30fps、H.264/AAC。系统画面由Chromium标签页原生媒体流连续采集，保留图谱、栈与流式组件动画。学生与教师两次真实Flash请求使用同一课程、学生和后续任务。浏览器回归与录制预检使用Mock。

演示依次展示错误作答、证据与路径、栈实验、学生附件辅导、理解检查、教师矩阵、AI教学规划、教案编辑、任务发布、学生完成及教师反馈。中间加入已生成会话的正常回看，供观众阅读真实解释和教学环节。随后说明方法对照，再回放约135秒的三条开发证据链。历史素材标明日期和发言者。

可编辑源位于[第七轮演示源](demo/第七轮演示源/)，包括连续录屏片段、事件、画板HTML与JSON、方法图、剪辑时间轴、独立旁白和字幕。分镜见[讲解稿与分镜](demo/讲解稿与分镜.md)，结果见[验收记录](demo/验收结果.json)。

```powershell
.venv/Scripts/python.exe scripts/assemble_round7_video.py
.venv/Scripts/python.exe scripts/generate_demo_narration.py
.venv/Scripts/python.exe scripts/assemble_demo_audio.py
```

剪辑脚本可直接使用交付的media目录重建，配音生成需要网络语音服务。先完成真实录屏与剪辑，再按实际时间轴编写解说。59句配音、87条底部字幕由同次TTS词边界生成，语音加速最大约1.17倍。音轨通过完整解码、音量检查和自动语音转写回验，画面按操作及开发阶段抽帧复核。

重新录制时，record-demo.mjs默认使用Mock，正式请求需显式设置DEMO_REAL与专用地址。真实开发联调账本限制总请求，当前轮次2/6次。录制控制器保存100%缩放及采集时实际视口，窗口共享提示条占用的高度作为媒体留边保留，界面导航和工作区完整可见。
