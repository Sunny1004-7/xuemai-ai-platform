# 前后端接口约定

所有路径以 `/api` 开头；除登录与 health 外需 `Authorization: Bearer <token>`。错误 `{detail: 中文说明}`。所有列表接口直接返回数组；dashboard、graph、analytics 返回对象。种子账号 teacher / student1 / student2，密码 `Xuemai123!`；数据是合成演示数据。

- `POST /auth/login {username,password}` → `{token,user:{id,name,role,username}}`。
- `GET /auth/me` → user；`POST /auth/logout`。
- `GET /courses` → `[{id,title,description,color,code,teacher_name,progress,knowledge_count}]`。
- `GET /courses/{id}` → course + `{chapters:[{id,title,position}],knowledge_points:[...],resources:[...]}`。
- `POST /courses {title,description?,code?}`；`PATCH /courses/{id}`。教师所有权验证。
- `GET /courses/{id}/graph` → `{nodes:[{id,title,chapter_id,description,x,y,mastery,status,resource_count}],edges:[{id,source,target}]}`。
- `POST /courses/{id}/chapters {title}`；`POST /courses/{id}/knowledge {title,description?,chapter_id?,x?,y?,prerequisite_ids?:number[]}`；`PATCH/DELETE /knowledge/{id}`。`POST /courses/{id}/edges {source,target}`，`DELETE /edges/{id}`。
- `GET /dashboard` → `{user,stats:{courses,study_minutes,completed_tasks,streak,mastery,students,assignments},courses,recommendations,assignments,recent_events,weekly_activity}`。
- `GET /questions?course_id=1&knowledge_id=&type=&difficulty=` → `[{id,course_id,knowledge_id,type,title,options:string[],difficulty,hints:string[],rubric,...}]`。学生不返回答案/解析；教师返回。
- `POST /questions {course_id,knowledge_id,type,title,options?,answer,explanation?,difficulty?,hints?,rubric?}`；`PATCH/DELETE /questions/{id}`。
- `POST /attempts {question_id,answer:string|string[],hints_used?:number,assignment_id?:number}` → `{id,correct,score,answer,explanation,error_type,mastery,review_status,recommendations}`。简答是待复核，不伪装确定性 AI 评分。
- `GET /attempts?course_id=` → 个人作答历史。
- 教师 `GET /attempts?course_id=` 返回本课程学生作答，含 `student_name,rubric,review_status`。`PATCH /attempts/{id}/review {score:0..100,feedback}` 明确采用教师评分，仅限主观题且一次复核；更新正式成绩、掌握度与分析，重复复核409。
- `GET /assignments?course_id=` → `[{id,title,course_id,class_id,knowledge_id,question_ids,student_ids,due_at,status,completed,submission_count,...}]`。
- `POST /assignments {course_id,title,question_ids:number[],class_id?:number,student_ids?:number[],knowledge_id?:number,due_at?:string,description?:string}`。教师可创建定向分层任务。
- `GET /assignments/{id}` → 作业 + `questions`；`GET /assignments/{id}/results` → 教师查看每名学生完成/分数。
- `GET /recommendations?course_id=1` → `[{id,knowledge_id,title,reason,kind:'practice'|'video'|'review',href,priority,mastery}]`。
- `GET /mistakes?course_id=` → `[{question_id,title,knowledge_id,knowledge_title,error_type,wrong_count,corrected,next_review_at,last_answer,options,type,...}]`；`POST /mistakes/{question_id}/review {answer,hints_used?}` 同 attempt。
- `GET /analytics?course_id=1` → `{summary:{student_count,average_mastery,attempt_count,accuracy},knowledge:[{id,title,average_mastery,weak_students:[{id,name,mastery}]}],students:[{id,name,mastery,attempts,accuracy}],error_distribution:[{name,value}],assignments:[...]}`。
- `POST /events {course_id,knowledge_id?,kind:'video_progress'|'video_checkpoint'|'experiment'|'hint'|'understanding',payload?:object}` → 保存事件；视频进度不能直接升掌握度。
- `GET /notes?course_id=1&resource_id=`；`POST /notes {course_id,resource_id?,knowledge_id?,timestamp?:number,content}`；`DELETE /notes/{id}`。
- `GET /resources?course_id=1&knowledge_id=&q=` → `[{id,title,kind,content,url,knowledge_id,version,metadata:object}]`；`POST /resources {course_id,title,kind,content?,url?,knowledge_id?,metadata?}`；`PATCH/DELETE /resources/{id}`；`POST /resources/upload` multipart `file,course_id,title,knowledge_id?`。
- `GET /classes?course_id=` → `[{id,name,course_id,join_code,students:[{id,name}]}]`；`POST /classes {course_id,name}`；`POST /classes/join {join_code}`；`POST /classes/{id}/members {student_id}`。
- `GET /classroom?course_id=1` → `[{id,course_id,title,prompt,kind,active,responses:[...]}]`；`POST /classroom {course_id,title,prompt,kind?}`；`POST /classroom/{id}/responses {answer}`；`PATCH /classroom/{id} {active}`。

视频种子资源 URL `/media/sorting-demo.mp4`，字幕、知识点时间轴与 checkpoint_question_id 存 metadata。AI 接口由 AI 模块约定并补充。

## 持久化编辑与个人计划扩展

- `PATCH /courses/{id}` 支持部分更新 `{title?,description?,code?,color?}`；重复课程代码409。
- 章节创建增加 `objectives:string[]`。`PATCH /chapters/{id} {title?,position?,objectives?}`；`DELETE /chapters/{id}` 保留知识点，将章节点关联置空。
- 知识点创建/修改增加 `objectives:string[]`，课程详情及图谱节点返回相同数组。`PATCH /knowledge/{id}` 是部分更新，可改位置坐标、目标、说明和章节；传 `prerequisite_ids:number[]` 原子替换入边，形成环路时422且全部回滚。
- `PATCH /classes/{id} {name}`；`DELETE /classes/{id}/members/{student_id}`；`DELETE /classes/{id}`。班级已有发布任务返回409，防止删除后任务变成整个课程可见。
- `PATCH /questions/{id}` 是部分更新；审核通过 `{status:'approved'}`，未审核 `{status:'draft'}`。学生列表不包含草稿且不能提交草稿。已用于作业或已有学习记录的题目禁止更改答案、题型、选项、知识点（409），请新建变式；已发作业题目不能撤回草稿。
- 题目选项必须非空且唯一；判断题恰好两项，多选答案非空、不重复且属于选项；填空/简答参考答案非空。简答默认提供100分量规，显式量规 criteria 必须为 `[{name,points}]` 且合计100。
- `PATCH /resources/{id}` 是部分更新。私有上传视频返回 `/api/resources/{id}/file`，须 Bearer 授权读取 Blob；只有本地合成演示视频公开。资源列表 metadata.resume_position 为当前学生上次保存的位置。

### 学生个人目标和计划

以下接口只向学生本人开放；教师403，另一学生无法读取或修改（404）。目标/计划与当前课程和知识点统一关联，跨课关系422。

- `GET /goals?course_id=1` → 数组；`POST /goals {course_id,title,description?,target_date?:'YYYY-MM-DD'|null,daily_minutes?:5..240,knowledge_ids?:number[],status?:'active'|'completed'|'paused'}` → 保存后的目标（含id/student_id/时间）。
- `PATCH /goals/{id}` 除 course_id 外支持部分更新；日期可置空；`DELETE /goals/{id}` 保留已有计划但解除 goal_id。
- `GET /plans?course_id=1` → 持久化计划数组；`POST /plans {course_id,title,description?,goal_id?,knowledge_id?,kind?:'practice'|'video'|'review'|'experiment'|'reading',scheduled_date?:'YYYY-MM-DD'|null,estimated_minutes?:1..240,status?:'planned'|'completed'|'skipped'}`。
- `PATCH /plans/{id}` 除 course_id 外支持部分更新；`DELETE /plans/{id}`。
- `GET /plan?course_id=1` → `{goals,items,recommendations,explanation}`。活动目标关联的知识点在动态推荐中增加优先级，并明确解释来自哪个个人目标。
- 标记计划完成只记录 `plan_completed` 自报事件，包含 `affects_mastery:false`，不把勾选完成当成独立掌握。真实掌握度仍由作答、提示、复测和教师主观复核证据更新。
