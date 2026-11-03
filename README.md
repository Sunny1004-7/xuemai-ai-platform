# 学脉 XueMai

面向师生的 AI 个性化智慧教育平台，为第九届传智杯 AI 创新应用挑战赛原创开发。课程、知识图谱、视频、习题、辅导和分层教学共享真实 SQLite 数据。

当前为0.1教学闭环验证版，87项后端测试、11项真实浏览器测试和算法验证通过。[技术文档PDF](docs/deliverables/xuemai-technical-report.pdf)与[交付版本](https://github.com/Sunny1004-7/xuemai-ai-platform/releases/tag/v0.1.0)提供源码包和6分35秒1080p演示。所有中文阶段提交与开发证据随仓库保留。

## 本机 10 分钟复现路径

环境：Windows 10/11，Python 3.13，Node.js 20.18+，npm，Git。开发机实际使用 Python 3.13、Node 20.18、npm 10.8；使用 Vite 6 保持兼容。首次依赖下载受网络影响，不保证所有网络环境在 10 分钟内完成。

```powershell
git clone https://github.com/Sunny1004-7/xuemai-ai-platform.git
cd xuemai-ai-platform
.\scripts\setup.ps1
.\scripts\start.ps1
```

打开 [学脉本机应用](http://127.0.0.1:5173)；[接口说明](http://127.0.0.1:8000/docs)。停止：`.\scripts\stop.ps1`。没有远程权限时，也可以直接在当前工程运行 setup/start。

| 身份 | 账号 | 演示密码 |
|---|---|---|
| 教师 林知远 | teacher | Xuemai123! |
| 学生 陈星河 | student1 | Xuemai123! |
| 学生 许沐晴 | student2 | Xuemai123! |

所有预置账号、掌握度、学习记录和班级均为**合成演示数据**。初始班级邀请码 XM2026；第二课程 Python 程序设计邀请码 PY2026。学生通过课程班级取得访问权限。

## 复现教学闭环

1. 教师登录，课程与班级创建课程、章节和班级，在图谱添加知识点和先修关系。
2. 题库与作业选择课程题目，发布到班级。学生登录后在练习页接收作业并提交。
3. 故意答错一次后查看错题；使用提示、独立复测，比较图谱掌握度和推荐理由变化。
4. 从题目打开学习伙伴，查看题目上下文、资料引用和流式回复，重新打开历史会话。
5. 在图谱选择冒泡排序并进入课程视频；字幕定位、时间戳笔记、随堂题写回学习记录。
6. 教师学情与分层页查看薄弱群组、发布巩固任务，学生完成后刷新统计。

交互实验室由真实算法执行排序、栈/队列、二叉树与 BFS，预测、步骤与结果相连。课程资料支持文本/PDF 解析；教师 AI 备课和出题先生成可编辑草稿，审核保存后才成为课程内容。

## AI 模式与额度

默认 `AI_MODE=mock`，无需密钥即可完整本地回归，界面明确标记本地演示。Mock 是固定教学样例，不冒充真实模型结果。

正式按需使用：把 `.env.example` 中所需变量设置到后端环境，或保留已被忽略的根目录 `deepseek官方api.txt`，然后：

```powershell
$env:DEEPSEEK_API_KEY = '<仅本机设置，不写入代码>'
.\scripts\start.ps1 -RealAI
```

`.env.example` 是变量清单，启动器不会自动解析 `.env`。密钥只在后端读取。模型、输出上限、超时与每分钟请求数均集中配置，默认不重试。模型依据 [DeepSeek 官方接口](https://api-docs.deepseek.com/zh-cn/)选择 `deepseek-flash`，结构化生成按 [JSON Output 规范](https://api-docs.deepseek.com/zh-cn/guides/json_mode/)校验。

常规测试、CI、浏览器回归均 **0 次真实请求**。真实烟测为显式单独命令，累计硬上限 5 次、发送前持久记账、异常即停止、单次最多 256 输出 Tokens；不要把烟测加入普通测试。2026-11-03 已完成连通性、流式、JSON 各 1 次，合计 3 次、220 Tokens。账本在被忽略的 `data/ai-smoke-ledger.json`，不可为重新测试而删除。

## 结构与验证

```text
backend/app/        认证、课程、评分、证据、推荐、教师分析、AI
backend/migrations/ 版本化 SQLite SQL
backend/tests/      离线契约、权限与业务闭环测试
backend/media/      自有教学演示 MP4
frontend/src/       学生与教师 React 页面、算法组件
frontend/e2e/       真实浏览器教学闭环
scripts/           Windows 安装启动测试、安全扫描、显式烟测
docs/              架构、API、设计与真实开发过程
```

```powershell
.\scripts\test.ps1
# 首次浏览器测试若缺少 Chromium：
cd frontend
npx playwright install chromium
```

后端测试使用隔离临时数据库；端到端使用独立端口和演示数据库，不访问真实 AI。测试报告和截图生成在忽略的本机目录，核实结果后把不含敏感信息的必要证据存入 docs。

数据库默认 `data/xuemai.db`，启动自动迁移及首次种子初始化。不要在已有真实数据上删除数据库以“修复”；演示重置请另选 `DATABASE_PATH` 创建新库。视频已随源码提供，重新生成需额外安装 `pillow imageio-ffmpeg` 后执行 `scripts/generate_demo_video.py`。

## 使用边界与赛事证据

客观题按规则评分，简答按量规待教师复核；AI 草稿和辅导需核对。观看时长仅作为活动记录，不能直接代表掌握。上传资源按课程授权访问，任何真实学生数据应在适当授权后导入。

本项目面向本机演示，服务默认仅绑定 127.0.0.1。公开部署前需要 HTTPS、账号管理、正式运维与数据保护配置；演示账号不适合直接用于公网服务。

运行setup前先停止本项目服务，避免Windows占用esbuild可执行文件；安装器会检查端口并说明。重新生成PDF和演示素材时，安装scripts/requirements-tools.txt中的可选工具；这些依赖不影响应用启动。原始聊天自动快照对部分协作正文不完整，另提供可见协作卡片逐字转存与实际回放，建议保留原界面截图交叉核验。

真实阶段进度见 [PROJECT_STATE.md](PROJECT_STATE.md)，架构与接口见 docs。开发过程摘要区分真实用户指令和 Codex 自主分工，不伪造用户反馈；原始聊天导出/录屏需与摘要共同保留。参赛要求包括 5–8 分钟 1080p MP4（至少 2 分钟真实 AI 协同）和不超过 30 页技术 PDF；最终交付状态以 PROJECT_STATE 为准。
