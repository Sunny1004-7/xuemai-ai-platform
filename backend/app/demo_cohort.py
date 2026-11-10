"""幂等、明确标识的合成教学样本；作答经正式评分和证据函数生成。"""
from datetime import timedelta
import json
import os
import random
from .evidence import utc_now

NAMES = ['沈知夏','许清越','周予安','宋书宁','陆景行','苏沐言','顾亦辰','叶初晴','江以南',
         '林晚舟','程思齐','温若溪','方明澈','秦望舒','唐一诺','贺云帆','白可欣','韩星澜',
         '孟子衿','何雨桐','杜嘉木','袁听澜','邵以恒','丁语棠','夏明轩','田乐之','吴念安']


def seed_cohort(db):
    if os.getenv('XUEMAI_DEMO_COHORT', '1') == '0':
        return
    if db.execute('SELECT 1 FROM content_revisions WHERE version=3001').fetchone():
        return
    from .learning import record_attempt
    from .common import save_assignment_baselines
    primary = db.execute("SELECT * FROM users WHERE username='student1' AND synthetic=1").fetchone()
    if not primary or not db.execute("SELECT 1 FROM courses WHERE id=1 AND code='CS201'").fetchone():
        return
    password = primary['password_hash']
    users = []
    for i, name in enumerate(NAMES):
        username = f'demo26_{i+1:02d}'
        db.execute("INSERT OR IGNORE INTO users(username,name,role,password_hash,synthetic) VALUES(?,?,'student',?,1)", (username,name,password))
        user = dict(db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone())
        db.execute('INSERT OR IGNORE INTO class_members VALUES(1,?)', (user['id'],))
        if i < 13:
            db.execute('INSERT OR IGNORE INTO class_members VALUES(2,?)', (user['id'],))
        users.append(user)
    rng = random.Random(20261110)
    base = utc_now().replace(hour=6,minute=0,second=0,microsecond=0) - timedelta(days=21)
    questions = [dict(q) for q in db.execute("SELECT * FROM questions WHERE course_id=1 AND status='approved' AND type='single' ORDER BY id")]
    py_question = db.execute('SELECT * FROM questions WHERE id=9').fetchone()
    tasks = []
    for day, title, qids in [(4,'线性结构阶段练习',[1,3,8]),(12,'图遍历与查找复测',[4,5,7])]:
        publish_at = base + timedelta(days=day)
        task = db.execute("INSERT INTO assignments(course_id,class_id,teacher_id,title,description,question_ids,student_ids,due_at,created_at) VALUES(1,1,1,?,?,?,?,?,?)",
            (title,'合成教学场景：追踪操作并解释边界条件。',json.dumps(qids),json.dumps([u['id'] for u in users]),(publish_at+timedelta(days=5)).isoformat(),publish_at.isoformat())).lastrowid
        tasks.append((day,task,qids))
    for day in range(21):
        for publish_day, tid, _ in tasks:
            if day == publish_day:
                save_assignment_baselines(db,tid,base+timedelta(days=day))
        for i,user in enumerate(users):
            persona = i % 6
            # 基础稳固、概念困难、步骤困难、迁移困难、提示依赖、近期低参与。
            if persona == 5 and day > 14 or (i+day)%5 == 0:
                continue
            moment = base + timedelta(days=day,hours=1,minutes=i*3)
            selected = rng.sample(questions, min(4,len(questions)))
            for publish_day, tid, qids in tasks:
                if day == publish_day + 2 and i%5 != 4:
                    selected += [dict(db.execute('SELECT * FROM questions WHERE id=?',(qid,)).fetchone()) for qid in qids[:(2 if i%4==1 else 3)]]
            for j,q in enumerate(selected):
                weakness = (persona==1 and q['skill']=='concept' or persona==2 and q['skill']=='procedure' or persona==3 and q['skill'] in ('reasoning','transfer'))
                chance = (.93 if persona==0 else .78) - (.48 if weakness else 0) + min(.12,day*.006)
                correct = rng.random() < chance
                expected = json.loads(q['answer'])
                options = json.loads(q['options'])
                wrong = next((o for o in options if o != expected),'需要继续推导')
                assignment = next((tid for d,tid,qs in tasks if day==d+2 and q['id'] in qs),None)
                hints = int(persona==4 or (not correct and rng.random()<.2))
                result = record_attempt(db,user,q,expected if correct else wrong,hints,assignment,moment+timedelta(minutes=j),False)
                db.execute("UPDATE learning_events SET payload=json_set(payload,'$.synthetic',json('true'),'$.sample_version',3001) WHERE json_extract(payload,'$.attempt_id')=?",(result['id'],))
            if i < 13 and day%4==0 and py_question:
                record_attempt(db,user,py_question,'int' if rng.random()<.8 else 'str',now=moment,include_recommendations=False)
            if day%3==i%3:
                payload=json.dumps({'synthetic':True,'resource_id':100,'watched_seconds':24,'current_time':24})
                db.execute("INSERT INTO learning_events(student_id,course_id,knowledge_id,kind,payload,created_at) VALUES(?,1,6,'video_progress',?,?)",(user['id'],payload,moment.isoformat()))
                db.execute("INSERT INTO learning_events(student_id,course_id,knowledge_id,kind,payload,created_at) VALUES(?,1,2,'experiment',?,?)",(user['id'],json.dumps({'synthetic':True,'mode':'stack','steps':5+i%6}),moment.isoformat()))
    activity = db.execute('SELECT id FROM classroom WHERE course_id=1 ORDER BY id LIMIT 1').fetchone()
    if activity:
        for i,user in enumerate(users[:23]):
            text = ['队列让较早发现的节点先扩展，因而逐层访问。','我仍需区分层序与深入探索。','用队列保存边界，访问标记避免重复。'][i%3]
            db.execute('INSERT OR IGNORE INTO classroom_responses(activity_id,student_id,answer,created_at) VALUES(?,?,?,?)',(activity[0],user['id'],text,(base+timedelta(days=20,hours=2)).isoformat()))
    db.execute('INSERT INTO content_revisions(version) VALUES(3001)')
