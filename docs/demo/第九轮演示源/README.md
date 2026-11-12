# 当前演示工程

本工程由docs/demo/current.json指定。成片473.47秒，1080p、30fps，系统界面259.5秒，真实开发档案135秒。沿用同一学生、课程与任务的教学过程，更新作品介绍、课前课中课后场景、统一框架和双主题登录镜头。新增DeepSeek请求0次。

## 重建

在工程根目录依次运行scripts/assemble_round9_video.py、scripts/generate_demo_narration.py --round 9和scripts/assemble_demo_audio.py。后两项默认读取当前版本配置。配音缓存绑定文案、声音、语速和WordBoundary，已有合成结果随工程提供。修改文案时重新运行配音步骤。scripts/audit_demo_audio.py使用本地Whisper small回验最终声音。

media保存本轮原始WebM、连续MP4、实际事件和时间轴。edit-timeline.json还引用第七、八轮演示源中的既有教学及开发素材，审阅包一并提供。scenes.json为当前讲稿，audio保留20语段音轨与边界，subtitles.srt与subtitles.ass分别用于单独阅读和烧录。通用SRT、ASS及分镜由同一生成流程同步。

## 框架与字幕

总框架母版为docs/technical-report/figures/overall-framework.tex。构建脚本导出实际节点锚点和七个语义分组，framework-focus.js根据图像容器的真实尺寸计算等比缩放、留白偏移、目标联合边界与8像素外边距。framework-phases.json根据同次语音边界确定讲解时刻，覆盖输入、共享证据、学生方法、教师方法、服务、工作区与反馈。验收关键帧保留每组开始、淡入中间和稳定状态。

字幕共72条，以语义停顿与Microsoft YaHei实际字宽划分，透明背景，单行显示。完整讲稿、语段、SRT、ASS及通用字幕保持对应。音量、解码、转写、画面与边界验收记录位于docs/rounds和docs/demo，人工听审状态如实记录。
