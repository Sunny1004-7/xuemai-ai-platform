"""第五版教学样例：正常启动自动补全，稳定键定位，一次导入不覆盖后续编辑。"""
import json
import os
from datetime import timedelta
from .evidence import utc_now
from .sample_python import UNITS

VERSION = 5001
SEED = 20261111


def encoded(value):
    return json.dumps(value, ensure_ascii=False)


def install_samples(db):
    if os.getenv('XUEMAI_DEMO_COHORT', '1') == '0' or db.execute('SELECT 1 FROM sample_packages WHERE version=?', (VERSION,)).fetchone():
        return
    primary = db.execute("SELECT * FROM users WHERE username='student1' AND synthetic=1").fetchone()
    if not primary:
        return
    from .ai_routes import ensure_ai_schema
    from .learning import record_attempt
    from .common import save_assignment_baselines
    ensure_ai_schema(db)
    base = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)

    def entity(key, table, values, match=None):
        # 不以标题重写用户内容；命中历史样例时只登记，不执行UPDATE。
        key = f'v5:{key}'
        previous = db.execute('SELECT entity_id FROM sample_entities WHERE sample_key=?', (key,)).fetchone()
        if previous:
            return previous[0]
        old = db.execute(f'SELECT id FROM {table} WHERE {" AND ".join(k+"=?" for k in match)}', tuple(match.values())).fetchone() if match else None
        item = old[0] if old else db.execute(f'INSERT INTO {table}({",".join(values)}) VALUES({",".join("?" for _ in values)})', tuple(values.values())).lastrowid
        db.execute('INSERT INTO sample_entities(sample_key,entity_table,entity_id,content_version) VALUES(?,?,?,?)', (key, table, item, VERSION))
        return item

    python = db.execute("SELECT * FROM courses WHERE code='CS101' AND teacher_id IN (SELECT id FROM users WHERE synthetic=1)").fetchone()
    if python:
        cid = python['id']
        points = {}
        specs = []
        for position, (chapter_title, units) in enumerate(UNITS, 1):
            chapter = entity(f'CS101:chapter:{position}', 'chapters', {'course_id': cid, 'title': chapter_title, 'position': position}, {'course_id': cid, 'title': chapter_title})
            for i, (title, explanation, prompt, options, answer, prerequisites) in enumerate(units):
                kid = entity(f'CS101:knowledge:{title}', 'knowledge_points', {'course_id': cid, 'chapter_id': chapter, 'title': title, 'description': explanation, 'difficulty': 1 + (position > 3), 'objectives': encoded([f'解释{title}的执行语义', '追踪示例并验证边界'])}, {'course_id': cid, 'title': title})
                points[title] = kid
                # 原始两节点属于明确已知的内置样例，仅调整章节关联，保留描述编辑。
                if title in ('变量与类型', '循环与条件'):
                    db.execute('UPDATE knowledge_points SET chapter_id=? WHERE id=?', (chapter, kid))
                specs.append((kid, prerequisites))
                skill = ['concept', 'procedure', 'reasoning', 'transfer'][i % 4]
                entity(f'CS101:question:{title}', 'questions', {'course_id': cid, 'knowledge_id': kid, 'type': 'single', 'title': prompt, 'options': encoded(options), 'answer': encoded(answer), 'explanation': explanation, 'difficulty': 1 + (position > 3), 'hints': encoded(['先写出每步的变量状态，再检查边界。']), 'skill': skill})
                entity(f'CS101:document:{title}', 'resources', {'course_id': cid, 'knowledge_id': kid, 'kind': 'document', 'title': title+'：例题与边界', 'content': f'# {title}\n\n{explanation}\n\n## 推导与例题\n{prompt}\n答案为{answer}。请在纸上逐步记录变量、容器内容或控制位置，比较各选项为什么成立或不成立。\n\n## 边界检查\n分别尝试空输入、一个元素和不合法输入。解释程序继续、跳过或终止的条件。\n\n## 独立迁移\n替换示例中的输入，再预测结果；先预测后运行，写出变化的原因。', 'metadata': encoded({'source': '本地编写教学样例', 'sample_version': VERSION, 'estimated_minutes': 6 + i})})
        for kid, prerequisites in specs:
            for prerequisite in prerequisites:
                db.execute('INSERT OR IGNORE INTO knowledge_edges(course_id,source,target) VALUES(?,?,?)', (cid, points[prerequisite], kid))
        # 仅移除自带旧模板留下的空章节；用户添加或已有内容的章节保留。
        db.execute("DELETE FROM chapters WHERE id=4 AND course_id=? AND title='程序基础' AND NOT EXISTS(SELECT 1 FROM knowledge_points WHERE chapter_id=4)",(cid,))
        extra = [
            ('multiple','列表遍历','以下哪些操作会修改原列表？',['append','sort','切片读取','len'],['append','sort'],'append追加元素，sort就地排序；读取切片和len不修改列表。'),
            ('true_false','元组与集合','元组的元素位置可以直接赋值修改。',['正确','错误'],'错误','元组是不可变序列。'),
            ('fill','字符串与切片','列表a=[0,1,2,3]，a[1:3]的结果为？',[],'[1, 2]','左闭右开，得到下标1和2。'),
            ('short','默认参数陷阱','解释为什么默认参数items=[]会跨调用共享内容，并给出修正方案。',[],'默认值定义时求值，改为None并在函数内新建列表','说明求值时机与修正方法。'),
            ('step','综合成绩分析','设计读取成绩文件并报告平均分的步骤，说明空文件与坏行的处理。',[],'读取；校验；转换；累计；检查计数；计算','先记录坏行，空有效数据明确返回状态，不除以0。'),
            ('multiple','异常处理','处理输入数字时哪些做法合理？',['捕获ValueError','提示重新输入','所有异常都忽略','用零替换所有坏数据'],['捕获ValueError','提示重新输入'],'在可恢复位置处理具体异常。')]
        for i, (kind, title, prompt, options, answer, explanation) in enumerate(extra):
            entity(f'CS101:extra:{i}', 'questions', {'course_id': cid, 'knowledge_id': points[title], 'type': kind, 'title': prompt, 'options': encoded(options), 'answer': encoded(answer), 'explanation': explanation, 'difficulty': 2 + (kind in ('short','step')), 'hints': encoded(['从定义和边界推导。']), 'skill': 'transfer' if kind in ('short','step') else 'reasoning', 'rubric': encoded({'criteria':[{'name':'解释机制','points':50},{'name':'边界与修正','points':50}],'total':100}) if kind in ('short','step') else '{}'})

    media = json.loads((__import__('pathlib').Path(__file__).resolve().parents[1] / 'media/python-teaching-metadata.json').read_text(encoding='utf8'))
    for course in db.execute("SELECT * FROM courses WHERE code IN ('CS201','CS101') AND teacher_id IN (SELECT id FROM users WHERE synthetic=1)").fetchall():
        cid, code = course['id'], course['code']
        nodes = [dict(n) for n in db.execute('SELECT * FROM knowledge_points WHERE course_id=? ORDER BY id', (cid,))]
        if code == 'CS101':
            for clip in media:
                node = next(n for n in nodes if n['title'] == clip['knowledge_title'])
                qid = db.execute("SELECT id FROM questions WHERE knowledge_id=? AND type='single' ORDER BY id LIMIT 1", (node['id'],)).fetchone()[0]
                meta = {k:v for k,v in clip.items() if k not in ('slug','knowledge_title','title')}
                meta.update(sample_version=VERSION, source='原创状态追踪教学短片', timeline=[{'time':0,'knowledge_id':node['id'],'title':node['title']},{'time':18,'knowledge_id':node['id'],'title':'边界与预测'}], checkpoints=[{'time':24,'question_id':qid}])
                entity(f'{code}:video:{clip["slug"]}', 'resources', {'course_id':cid,'knowledge_id':node['id'],'title':clip['title'],'kind':'video','url':'/media/'+clip['slug']+'.mp4','content':node['description'],'metadata':encoded(meta)})
        chapters = db.execute('SELECT * FROM chapters WHERE course_id=? ORDER BY position', (cid,)).fetchall()
        for chapter in chapters:
            node = next((n for n in nodes if n['chapter_id'] == chapter['id']), nodes[0])
            entity(f'{code}:lesson:{chapter["id"]}', 'resources', {'course_id':cid,'knowledge_id':node['id'],'kind':'lesson_plan','title':chapter['title']+'教学活动设计','content':f'# {chapter["title"]}\n\n教学目标：用可复算的状态追踪解释{node["title"]}，识别边界并迁移到新输入。\n\n1. 用{node["description"]}建立问题情境。\n2. 学生先独立预测，再分组解释每步变化。\n3. 对照易错输入与反例，讨论隐含前提。\n4. 完成关联练习，教师根据错误步骤安排复测。\n\n评价：关注推理依据、独立完成情况和边界处理，避免只检查最后答案。', 'metadata':encoded({'source':'本地编写教学方案','sample_version':VERSION})})
        questions = [dict(q) for q in db.execute("SELECT * FROM questions WHERE course_id=? AND status='approved' ORDER BY id", (cid,))]
        objective = [q for q in questions if q['type'] not in ('short','step')]
        videos = [dict(r) for r in db.execute("SELECT * FROM resources WHERE course_id=? AND kind='video' ORDER BY id", (cid,))]
        group = db.execute('SELECT * FROM classes WHERE course_id=? ORDER BY id LIMIT 1', (cid,)).fetchone()
        members = [dict(u) for u in db.execute('SELECT u.* FROM users u JOIN class_members m ON m.student_id=u.id WHERE m.class_id=? AND u.synthetic=1 AND u.active=1 ORDER BY u.id', (group['id'],))]
        tasks = []
        for i, title in enumerate(['基础概念与执行追踪','边界条件阶段测验','薄弱知识巩固任务']):
            qs = [q['id'] for q in objective[i*3:i*3+4]]
            tid = entity(f'{code}:task:{i}', 'assignments', {'course_id':cid,'class_id':group['id'],'teacher_id':course['teacher_id'],'title':title,'description':'逐步写出状态，独立完成后解释边界。','question_ids':encoded(qs),'student_ids':'[]','created_at':(base-timedelta(days=12-i*4)).isoformat(),'due_at':(base+timedelta(days=i*3-3)).isoformat()})
            save_assignment_baselines(db, tid, base-timedelta(days=12-i*4))
            tasks.append((tid, qs))
        # 同一学生按时间顺序写入正式评分函数；不以掌握度常量填充图表。
        for member_index, member in enumerate(members):
            count = 24 if member['id'] == primary['id'] else 12
            from .evidence import parse_time
            latest = db.execute('SELECT MAX(a.created_at) FROM attempts a JOIN questions q ON q.id=a.question_id WHERE a.student_id=? AND q.course_id=?', (member['id'], cid)).fetchone()[0]
            start = max(base-timedelta(days=11), parse_time(latest)+timedelta(seconds=1)) if latest else base-timedelta(days=11)
            end = max(start, utc_now()-timedelta(minutes=10))
            for i in range(count):
                key = f'v5:{code}:attempt:{member["id"]}:{i}'
                if db.execute('SELECT 1 FROM sample_entities WHERE sample_key=?', (key,)).fetchone():
                    continue
                q = objective[i % len(objective)]
                expected = json.loads(q['answer']); options = json.loads(q['options'])
                wrong = next((o for o in options if o != expected), '边界待检查') if q['type'] != 'multiple' else []
                success = (i + member_index) % 5 not in (0, 1)
                task = next((tid for t,(tid, qs) in enumerate(tasks[:2]) if q['id'] in qs and (i>=12 or t==0)), None)
                moment = start + (end-start)*i/max(1,count-1)
                if task:
                    published = parse_time(db.execute('SELECT created_at FROM assignments WHERE id=?',(task,)).fetchone()[0])
                    if moment < published: task=None
                result = record_attempt(db, member, q, expected if success else wrong, int(i%7==0), task, moment, False)
                db.execute('INSERT INTO sample_entities(sample_key,entity_table,entity_id,content_version) VALUES(?,?,?,?)', (key, 'attempts', result['id'], VERSION))
                db.execute("UPDATE learning_events SET payload=json_set(payload,'$.synthetic',json('true'),'$.sample_version',?) WHERE json_extract(payload,'$.attempt_id')=?", (VERSION,result['id']))
        subjective = next(q for q in questions if q['type'] in ('short','step'))
        if not db.execute('SELECT 1 FROM sample_entities WHERE sample_key=?',(f'v5:{code}:subjective',)).fetchone():
            result=record_attempt(db, dict(primary), subjective, '我先检查前提与边界，再根据每步状态解释结果。还需要补充反例。', now=utc_now()-timedelta(minutes=5), include_recommendations=False)
            db.execute('INSERT INTO sample_entities(sample_key,entity_table,entity_id,content_version) VALUES(?,?,?,?)',(f'v5:{code}:subjective','attempts',result['id'],VERSION))
        goals=[]
        focus_nodes = [nodes[i] for i in [0, min(5,len(nodes)-1), min(12,len(nodes)-1), min(20,len(nodes)-1)]]
        for i, node in enumerate(focus_nodes):
            goals.append(entity(f'{code}:goal:{i}', 'learning_goals', {'student_id':primary['id'],'course_id':cid,'title':'掌握'+node['title']+'与边界','description':'能独立追踪典型例子，并解释新输入的结果。','daily_minutes':[20,30,40,25][i],'knowledge_ids':encoded([node['id']]),'status':'completed' if i==3 else 'active','target_date':(base+timedelta(days=5+i*3)).date().isoformat()}))
        for i in range(12):
            q=objective[i%len(objective)]; node=next(n for n in nodes if n['id']==q['knowledge_id']); kind=['practice','video','reading','experiment'][i%4]
            target={'question_id':q['id'],'completion_kind':'attempt'}
            if kind=='video':
                video=videos[(i//4)%len(videos)]; node=next(n for n in nodes if n['id']==video['knowledge_id']); target={'resource_id':video['id'],'video_timestamp':0,'completion_kind':'video_progress','required_seconds':20}
            if kind=='reading':
                resource=db.execute("SELECT id FROM resources WHERE knowledge_id=? AND kind='document' ORDER BY id",(node['id'],)).fetchone(); target={'resource_id':resource[0],'completion_kind':'self_report'}
            if kind=='experiment':
                node=next(n for n in nodes if n['title']==('循环与条件' if code=='CS101' else '冒泡排序')); target={'experiment_id':'py-loop' if code=='CS101' else 'sort','completion_kind':'experiment'}
            pid=entity(f'{code}:plan:{i}', 'study_plans', {'student_id':primary['id'],'course_id':cid,'goal_id':goals[i%4],'knowledge_id':node['id'],'title':['独立练习：','观看片段：','精读讲义：','逐步实验：'][i%4]+node['title'],'description':'执行后核对边界，记录理解变化。','kind':kind,'scheduled_date':(base+timedelta(days=i//3-1)).date().isoformat(),'estimated_minutes':[6,4,8,5][i%4],'status':'planned','target':encoded(target)})
            if i==2 and not db.execute('SELECT 1 FROM sample_entities WHERE sample_key=?',(f'v5:{code}:plan-self-report',)).fetchone():
                eid=entity(f'{code}:plan-self-report','learning_events',{'student_id':primary['id'],'course_id':cid,'knowledge_id':node['id'],'kind':'plan_completed','payload':encoded({'plan_id':pid,'self_reported':True,'affects_mastery':False}),'created_at':(base-timedelta(hours=1)).isoformat()})
                db.execute("UPDATE study_plans SET status='completed',completion_event_id=? WHERE id=?",(eid,pid))
        for i, node in enumerate(focus_nodes + [nodes[-1]]):
            conversation=entity(f'{code}:conversation:{i}', 'ai_conversations', {'user_id':primary['id'],'course_id':cid,'title':node['title']+'：从例子到边界','context':encoded({'course_id':cid,'knowledge_point_id':node['id'],'sample_source':'本地编写教学历史','sample_version':VERSION}),'created_at':(base-timedelta(days=5-i)).isoformat()})
            messages=[('user','我理解了定义，但不知道怎样检查'+node['title']+'的边界。'),('assistant',node['description']+'\n先把输入和初始状态列出来，每执行一步只改变对应变量。请先预测一个最小输入的结果。'),('user','如果输入为空，是否还应该继续执行？'),('assistant','先判断操作的前提。空输入没有可处理元素，需要明确返回空结果或无数据状态；不能用默认的成功值代替。再尝试一个元素，对照循环或函数的终止条件。')]
            for j,(role,text) in enumerate(messages):
                entity(f'{code}:message:{i}:{j}', 'ai_messages', {'conversation_id':conversation,'role':role,'content':text,'mode':'sample','created_at':(base-timedelta(days=5-i)+timedelta(minutes=j)).isoformat()})
        for i, kind in enumerate(['question','quiz','feedback','question']):
            node=focus_nodes[i]
            aid=entity(f'{code}:classroom:{i}', 'classroom', {'course_id':cid,'title':node['title']+['预测讨论','边界小测','学习反馈','迁移讨论'][i],'prompt':'请结合一个具体输入，解释'+node['title']+'的状态变化，并指出容易忽略的边界。','kind':kind,'active':int(i==0),'created_at':(base-timedelta(days=i+1)).isoformat()})
            for j,member in enumerate(members[:10]):
                db.execute('INSERT OR IGNORE INTO classroom_responses(activity_id,student_id,answer,created_at) VALUES(?,?,?,?)',(aid,member['id'],f'我用{j+1}个元素验证。'+node['description']+['还需进一步比较空输入。','关键在于先验证前提。','我用状态表确认每一步。'][j%3],(base-timedelta(days=i+1)+timedelta(minutes=15+j)).isoformat()))
        for i,video in enumerate(videos[:3]):
            entity(f'{code}:note:{i}', 'notes', {'student_id':primary['id'],'course_id':cid,'knowledge_id':video['knowledge_id'],'resource_id':video['id'],'timestamp':10+i*3,'content':'这里的关键是记录每一步状态，再与边界条件对照。','created_at':(base-timedelta(days=2-i)).isoformat()})
            entity(f'{code}:video-event:{i}', 'learning_events', {'student_id':primary['id'],'course_id':cid,'knowledge_id':video['knowledge_id'],'kind':'video_progress','payload':encoded({'resource_id':video['id'],'current_time':20,'watched_seconds':20,'synthetic':True,'sample_version':VERSION}),'created_at':(base-timedelta(days=2-i)).isoformat()})
        entity(f'{code}:experiment', 'learning_events', {'student_id':primary['id'],'course_id':cid,'knowledge_id':focus_nodes[1]['id'],'kind':'experiment','payload':encoded({'mode':'py-loop' if code=='CS101' else 'sort','steps':6,'prediction_correct':False,'synthetic':True,'sample_version':VERSION}),'created_at':(base-timedelta(days=1)).isoformat()})
    db.execute('INSERT INTO sample_packages(version,seed,time_base) VALUES(?,?,?)',(VERSION,SEED,base.isoformat()))
