# 第八轮演示工程

正式成片473.47秒，系统操作259.5秒，真实开发档案135秒。素材来自原生标签页媒体流，原始WebM、连续MP4与事件一并保存。boards是封面等说明素材，boards-patch是重新适配后的完整框架与三条开发档案，tour是本轮新增的只读与反馈操作。实际剪辑以edit-timeline.json为准。

已有真实学生辅导、教师教学规划及任务素材位于相邻第七轮演示源/media，时间轴以仓库相对路径引用。本轮没有新增DeepSeek请求。原始响应、用量、任务与开发记录另见docs/rounds及docs/development-process。开发画面标识原始日期和实际发言者。

在项目根目录依次运行scripts/assemble_round8_video.py、scripts/generate_demo_narration.py --round 8，再设置XUEMAI_VIDEO_ROUND=8运行scripts/assemble_demo_audio.py。具备缓存模型时运行scripts/audit_demo_audio.py作自动回验。依赖见scripts/requirements-tools.txt。

母版图为docs/technical-report/figures/overall-framework.tex，作者与作品字段来自docs/submission-facts.json，product.json由框架构建脚本同步。boards.html是可交互的讲解与开发记录展示，boards.json包含公开协作原文节选和实际Git差异。讲稿及语段在scenes.json，audio下保留MP3、WAV、WordBoundary及摘要，字幕同时提供SRT与透明底ASS。完整旁白为audio/narration-complete.wav。

神经合成人声采用云希、-3%语速，20个完整语段，93条字幕。自动解码、音量、语音回转写与画面复核已经完成，未作人工听审。最终MP4及摘要以docs/demo/验收结果.json为准。
