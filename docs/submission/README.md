# 学脉 XueMai：复现性声明与重现指南

　　学脉面向课程学习、个性化辅导与教学协作，采用React、TypeScript、FastAPI和SQLite。源码包含课程初始化数据、六段原创教学短片、师生业务模块、核心算法、自动化测试及文档与视频制作源文件。预置班级与学习记录用于演示，数据结构与算法、Python程序设计为示例课程。

## 提交材料

| 官方要求 | 文件或入口 |
|---|---|
| 当前系统源码 | [学脉XueMai-完整源码.zip](学脉XueMai-完整源码.zip) |
| Public仓库及完整提交历史 | [GitHub仓库](https://github.com/Sunny1004-7/xuemai-ai-platform)、[提交历史](https://github.com/Sunny1004-7/xuemai-ai-platform/commits/main/)、[Git提交记录](Git演进记录/Git提交记录.txt) |
| 三条核心功能的Prompt提问、AI反馈与修复过程 | [AI协同开发记录](AI协同开发记录/README.md)、[逐字转存原文](AI协同开发记录/004-核心功能实际协作逐字转存.md) |
| 复现性声明与10分钟运行指南 | 本README、源码根目录README、依赖清单与环境变量模板 |
| 不超过30页的技术文档 | [学脉XueMai-技术文档.pdf](学脉XueMai-技术文档.pdf) |
| 5—8分钟、1080p有声视频，含至少2分钟AI协同过程 | [学脉XueMai-演示视频-含旁白.mp4](学脉XueMai-演示视频-含旁白.mp4) |

## 10分钟极速复现

　　运行环境为Windows 10/11、Python 3.13、Node.js 20.18或更高版本、npm和Git。解压源码ZIP后进入其中的`xuemai`目录，右键打开PowerShell，执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start.ps1 -MockAI
```

　　也可双击源码根目录的“启动学脉.cmd”。启动器会准备缺少的依赖并打开浏览器。应用地址为http://127.0.0.1:5173，后端接口说明为http://127.0.0.1:8000/docs。停止服务使用：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/stop.ps1
```

| 身份 | 账号 | 密码 |
|---|---|---|
| 教师 | teacher | Xuemai123! |
| 学生 | student1 | Xuemai123! |

　　初次运行自动创建SQLite数据库并导入两门课程、知识网络、题目、资料、教学任务与合成学情。班级邀请码为XM2026和PY2026。数据库默认保存在`data/xuemai.db`；将`DATABASE_PATH`设为新文件路径即可独立初始化。

## 依赖与环境变量

　　源码中的`backend/requirements.txt`列出后端依赖，`frontend/package.json`与`frontend/package-lock.json`分别保存前端依赖及锁定版本，`.env.example`提供配置模板。安装脚本使用这些文件完成依赖准备。普通运行包含所需教学视频，无需重新制作媒体。

　　离线体验和自动化测试使用Mock。启用DeepSeek官方服务时，先停止已有服务，在PowerShell中配置后端密钥并启动：

```powershell
$env:DEEPSEEK_API_KEY = '<填写有效密钥>'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start.ps1 -RealAI
```

　　主要环境变量为`AI_MODE`（auto、mock、real）、`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`及`DATABASE_PATH`。具体默认值见`.env.example`。模板由进程环境配置，不自动把`.env`文件导入PowerShell。参赛源码不包含API Key，密钥仅由后端读取。

　　语音输入采用可选本地Whisper模型，使用`powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/setup-voice.ps1`准备额外依赖和模型。课程、图谱、实验、练习及Mock教学流程可直接运行。

## 教学过程与验证入口

1. 学生查看学习概览与计划，进入知识网络、课程资料、视频、练习和AI学习伙伴。
2. 教师查看班级学情、知识矩阵与作答证据，使用AI教学助手形成可编辑安排。
3. 教师审核并发布任务，学生完成后，教师查看结果和后续反馈。

　　在源码根目录执行`powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/test.ps1`运行自动化验证。后端业务测试采用隔离数据库，浏览器测试使用独立端口和Mock。已有算法实验、真实模型请求记录与Token账本位于`docs/experiments/round10/`，方法说明见`docs/ALGORITHMS_V10.md`，实际验证记录见`docs/VALIDATION.md`。

## 源码与演进记录

　　源码ZIP是当前Git提交的文件快照，内含`源码版本.txt`和`Git提交记录.txt`。完整细粒度历史保存在Public仓库；需要逐提交复现时执行：

```powershell
git clone https://github.com/Sunny1004-7/xuemai-ai-platform.git
cd xuemai-ai-platform
git log --oneline
```

　　AI记录分别保留原始要求、可见协作原文与自动导出的公开快照。三条核心链围绕课程与权限、练习与学习证据、DeepSeek辅导展开，记录中的历史指令与用量对应当时开发阶段。自动导出的部分协作正文不可读，来源说明已保留；三条功能链的可见逐字转存独立提供。演示视频展示真实历史记录的复现过程。

　　参赛学生：刘嘉程；学校：西安交通大学；专业：软件工程；指导教师：刘帅。
