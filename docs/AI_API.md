# AI 接口与成本控制

所有接口需要 Bearer 会话。默认 `AI_MODE=mock`，后端明确返回 mode；Mock 不是 DeepSeek 实时回答。

| 接口 | 输入/输出 |
|---|---|
| GET /api/ai/status | mode、model、configured、max_tokens、requests_per_minute、note |
| GET /api/ai/conversations?course_id=1 | 当前用户在课程内的会话数组 |
| GET /api/ai/conversations/{id} | 会话和 messages 数组；每条含 role、content、citations、mode |
| POST /api/ai/chat | course_id、message、conversation_id?、knowledge_id?、question_id?、resource_id?、video_timestamp? |
| POST /api/ai/generate | 仅教师：course_id、kind(question/lesson/rubric)、knowledge_id?、question_id?、answer?、prompt? |

chat 为 SSE：meta 含 conversation_id/mode/citations；delta 含 content；done 含 usage/next_action；error 含中文 message/code/retryable。引用含 id/resource_id/title/excerpt/url。

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
