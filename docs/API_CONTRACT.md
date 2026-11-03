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
