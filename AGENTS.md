# 学脉工程协作约定

执行范围和功能要求以 CODEX_TASK.md 为依据，交付状态见 PROJECT_STATE.md。保护根目录 API Key，常规测试使用 Mock。所有 Git 提交信息使用中文，并对应实际可验证的修改。

## 每轮交付

用户要求从2026年11月10日起，每轮完成修改后生成当前系统完整审阅ZIP，放入根目录“交付审阅包”，文件名包含北京时间日期及时分秒。每轮必须重新对当前前端全部模块进行完整详细截图，并放入该轮ZIP，方便审阅GPT直接检查界面。

1. 为本轮新增 docs/rounds/ 修改记录，写明实际需求、实现、验证结果和遗留事项，更新 PROJECT_STATE.md。
2. 执行 `node frontend/scripts/capture-review.mjs docs/rounds/本轮记录.md`。截图工具先构建当前前端，再以独立数据库、隔离端口和Mock逐页操作。按照 frontend/scripts/review-capture-plan.json 覆盖登录页、学生端及教师端全部模块，保存桌面、手机窄屏全页图、长页分段和关键弹窗及结果图。新增导航或交互时同步补齐截图计划与执行逻辑。
3. 检查截图索引和原图，验证本轮改动并完成中文阶段提交。界面或业务源码再次变更后重新运行截图。
4. 执行 `.venv/Scripts/python.exe scripts/package_review.py --record docs/rounds/本轮记录.md --base-ref 本轮开始时的Git提交 --screenshots 交付审阅包/本轮截图目录`。必须传入本轮成功截图的目录，工具校验模块覆盖、源码指纹、PNG尺寸和SHA256。
5. 确认审阅包包含当前完整源码、文档、现有视频、本轮记录、补丁和“界面截图”，检查ZIP完整性及文件清单校验。截图总览HTML、Markdown索引和JSON清单随图收录。
6. 在回复中提供本轮ZIP的可点击绝对路径和实际截图数量。

打包脚本会收录符合规则的未跟踪源文件，生成文件摘要、Git演进记录和审阅入口。凭据、依赖、运行数据、缓存、历史压缩包及“交付审阅包”目录由源码遍历规则过滤。本轮截图通过显式参数单独收录，避免压缩包递归套入。历史审阅包保留。

## Windows启动

根目录“启动学脉.cmd”供人工双击，使用 Windows PowerShell 启动前后端并打开浏览器。脚本应兼容中文及带空格路径，重复启动复用本项目服务，端口冲突给出可操作错误。PowerShell入口及其调用脚本采用UTF-8 BOM，兼容Windows PowerShell 5.1。
