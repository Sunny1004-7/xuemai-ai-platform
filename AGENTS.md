# 学脉工程协作约定

执行范围和功能要求以 CODEX_TASK.md 为依据，交付状态见 PROJECT_STATE.md。保护根目录 API Key，常规测试使用 Mock。所有 Git 提交信息使用中文，并对应实际可验证的修改。

## 当前交付约定

用户于2026年11月18日更新交付要求，后续按以下方式执行。

1. 修改后更新docs/rounds中的记录和PROJECT_STATE.md，按实际阶段使用中文Git提交并推送。
2. 使用已有完整界面图，针对改动进行必要的页面或视频关键帧检查。
3. 后续取消全量系统截图、完整审阅ZIP和反复的文件哈希核验。
4. 正式成品同步至根目录“最终参赛提交材料”。该目录只保留最终提交文件，视频仅保留有语音讲解的正式版本。制作源、字幕、无声中间片和验证记录保存在工程目录。
5. 用户进一步要求集中全部官方材料，正式目录提供六个可直接提交文件：当前源码ZIP、README、AI协同开发记录ZIP、Git演进记录TXT、PDF及唯一的有声MP4。源码ZIP由scripts/prepare_submission.py从已提交Git树生成，不是逐轮审阅包；保留当前运行及制作资产，旧轮媒体通过Public仓库历史提供。完整Git历史继续保留在Public仓库，ZIP内附提交记录与源码版本。全面检查入口为scripts/audit_official_submission.py。

## Windows启动

根目录“启动学脉.cmd”供人工双击，使用 Windows PowerShell 启动前后端并打开浏览器。脚本应兼容中文及带空格路径，重复启动复用本项目服务，端口冲突给出可操作错误。PowerShell入口及其调用脚本采用UTF-8 BOM，兼容Windows PowerShell 5.1。
