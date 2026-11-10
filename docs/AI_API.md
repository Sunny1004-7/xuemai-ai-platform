# AI 接口与成本控制

所有接口需要 Bearer 会话。默认 `AI_MODE=auto`，有后端Key时使用real，无Key时使用mock；自动化测试显式设置mock。后端明确返回mode，Mock为固定教学样例。

| 接口 | 输入/输出 |
|---|---|
| GET /api/ai/status | mode、model、configured、max_tokens、requests_per_minute、note |
| GET /api/ai/conversations?course_id=1 | 当前用户在课程内的会话数组 |
| GET /api/ai/conversations/{id} | 会话和 messages 数组；每条含 role、content、citations、mode |
| POST /api/ai/chat | course_id、message、conversation_id?、knowledge_id?、question_id?、resource_id?、video_timestamp? |
| POST /api/ai/generate | 仅教师：course_id、kind(question/lesson/rubric)、knowledge_id?、question_id?、answer?、prompt? |

chat 为 SSE：meta 含 conversation_id/mode/citations；delta 含 content；done 含 usage/next_action；error 含中文 message/code/retryable。引用含 id/resource_id/title/excerpt/url。

## 0.2结构化动作与理解检查

完整回答的`done.teaching`和会话历史中每条消息的`teaching`保存策略与动作。动作类型由模型在后端提供的候选中选择，后端映射到当前课程的概念对照、视频、实验或检查题；不直接执行模型输出的URL或对象编号。候选选择无效时回落到受支持的教学安排。

- `POST /api/ai/checks/{check_id}/answer {answer,hints_used?}`：学生本人提交已关联的检查题，复用作答评分、学习证据与复习调度，另返回`next_action:{title,href}`。正确进入间隔复测，仍有困难进入先修与概念对照。重复提交409，非本人或不可访问的对象404。
- `GET /api/ai/checks/{check_id}`：返回`{result:null|{correct,score,explanation,evidence,review_schedule}}`，用于重新打开历史时恢复结果。

资源引用增加版本信息。上传、编辑、删除时写入索引变更，检索消费变更并保留资源版本；未变内容不会在每次辅导时重建。检索结果和学习状态仍受用户与课程权限限制。

generate 输出 `{mode,kind,draft:true,review_status:'pending_teacher_review',result,citations,usage}`。
question result 可编辑后保存题库；lesson result 可编辑后保存资料；rubric 分数仅建议，必须教师复核。Mock 量规分数是演示样例，不能用于真实评分。

## 真实模式

后端设置 AI_MODE=real，密钥通过 DEEPSEEK_API_KEY（或根目录已忽略的本地文件）读取。浏览器不传密钥。
当前模型配置 `deepseek-flash`；依据 [DeepSeek 官方接入文档](https://api-docs.deepseek.com/zh-cn/) 与 [JSON 输出文档](https://api-docs.deepseek.com/zh-cn/guides/json_mode/)，于 2026-11-03 核对。
参数集中管理，默认 768 输出 Tokens、35 秒超时、每用户每分钟 6 次，无自动重试。日志在被忽略的 data/ai-usage.jsonl，仅记时间、模式、状态、用量，不记录密钥和原始问答。

## 小规模开发联调

常规 pytest/浏览器回归不调用真实 API。仅手动显式执行：

```powershell
.venv/Scripts/python.exe scripts/ai_smoke.py --kind connectivity --run
.venv/Scripts/python.exe scripts/ai_smoke.py --kind stream --run
.venv/Scripts/python.exe scripts/ai_smoke.py --kind structured --run
```

每次发送前写 data/ai-smoke-ledger.json，累计最多 5 次，每次最多 256 输出 Tokens；异常停止后续调用，不自动重试。账本中的 reserved 表示已计数且未确认完成，不能当作未调用而重置。真实开发联调账本与正式按需使用日志分开。
运行锁残留说明先前进程中断：先核实没有进程运行，再清理 `.running`；保留 ledger 中既有调用计数。

## 0.3协作编排与独立联调

DIA-GUIDE在done.teaching.collaboration与历史消息中保存诊断、策略、校验和角色轨迹。规则诊断读取已评分证据、先修和上轮反馈，策略代理指导一次模型生成，规则校验检查课程对象、理解检查和引用。检查结果写入teaching_runs，下一轮同知识失败时优先转向实验表征。正式成稿用校验后的content覆盖流式临时文本。

0.3已用scripts/validate_live_ai.py完成4次代表性抽样，覆盖协作辅导、出题、备课和量规评阅，输入3744、输出724 Tokens，零重试。使用独立data/ai-smoke-round3.json，保留原历史账本；若该轮账本已存在，脚本直接停止。开发抽样上限与产品正常教学调用分开，不能将历史3/5理解为产品永久限额。
