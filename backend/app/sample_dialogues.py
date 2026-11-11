"""人工编写的差异化教学对话；5002只升级未编辑的5001模板文字。"""
import json
DIALOGUES={
 'CS101':[
 ('循环与条件','range的右端点为什么不取',[
 'for i in range(1,4)为什么只得到1、2、3？我以为4也包含。',
 'range采用左闭右开区间。这里从1开始，达到4前停止，所以共有3个整数。可以把循环条件写成i<4，再逐个检查1、2、3是否满足。',
 '那么求1到4的和，应该用range(1,5)，结果是10，对吗？',
 '对。上界改成5后才包含4。还可以用range(4,4)检查空区间：一次也不执行，累计变量仍保留初值。'],
 '写清循环范围与累加边界','分别追踪空区间、单个元素与多个元素，说明每轮total与已处理项的关系。'),
 ('列表切片与别名','修改副本为何影响原列表',[
 'a=[1,2]，b=a，执行b.append(3)后a也变了，这是复制失败吗？',
 'b=a只是让两个名称指向同一个列表，没有创建副本。通过b追加后，a观察到的仍是该列表。若需要新的外层列表，可以写b=a[:]。',
 '若a=[[1],[2]]，切片复制后执行b[0].append(9)，原列表为什么还会改变？',
 '切片是浅拷贝：外层列表不同，内层的[1]仍被共享。修改内层会同时被观察到；直接替换b[0]则只改变新外层的引用。先画出两层对象连接再判断。'],
 '区分列表别名与浅拷贝','用追加、元素替换与嵌套列表三个例子解释对象共享，完成列表结果预测。'),
 ('默认参数陷阱','默认列表为何跨调用累积',[
 'def collect(x,items=[]): items.append(x); return items，第二次调用为什么还有上一次的值？',
 '默认值在函数定义时求值，而不是每次调用时新建。未传items的多次调用使用同一个列表，append会保留修改。先不要删除历史值，检查对象是在什么时候创建的。',
 '改成items=None，再在函数内判断并创建空列表，是否就可以分开？',
 '可以。每次省略参数时，在本次调用里创建新列表。若调用方显式传入列表，仍会修改调用方的对象；这是另一条需要说明的接口约定。'],
 '解释参数绑定与可变默认值','对比省略参数、传入新列表、重复传入同一列表三种调用，给出None默认值方案。'),
 ('文本解析','成绩文件遇到坏行如何继续',[
 '一行成绩是“李明,85”，能否直接split后把第二项转成整数？',
 '先检查字段数量并去除空白，再转换成绩。空行和缺字段应单独记录；数值转换可能发生ValueError，应在能够提示或跳过该行的位置处理。',
 '若没有任何有效成绩，我返回平均分0可以吗？',
 '应返回“没有有效数据”的明确状态，避免把没有数据解释成成绩为0。累计有效条数后先检查是否大于0，再计算平均分；坏行记录保留行号以便修正。'],
 '完成文件解析与异常边界检查','读取并校验成绩行，分别处理坏行、空文件与有效数据，说明统计结果的含义。'),
 ('字典计数','统计频次为何使用get',[
 '第一次遇到单词时，counts[word]+=1为什么会出错？',
 '字典中还没有这个键，直接读取会出现KeyError。counts[word]=counts.get(word,0)+1表示先读取已有次数，缺失时从0开始。',
 '输入a、a、b后，a为2、b为1；如果需要按次数排序呢？',
 '可以对items按次数降序排序，并定义次数相同时的词语顺序。计数与展示分成两步，空输入则得到空字典与空列表。'])],
 'CS201':[
 ('数组与链表','插入位置与移动成本',[
 '数组和链表都能插入，为什么说数组中间插入更慢？',
 '数组元素连续存放，在下标i插入需要为新元素腾出位置，后面元素通常要移动。链表若已找到前驱节点，修改连接即可，但寻找该位置本身仍需时间。',
 '所以链表按下标访问也不是常数时间？',
 '对。普通单链表按下标查找要从头逐步移动，不能把“改连接快”理解为任意位置访问快。请把定位成本与实际修改成本分开比较。'],
 '比较线性结构的定位与修改成本','分别说明按下标读取、中间插入和连续遍历的代价，选择合适的数据结构。'),
 ('栈与队列','交错出入操作的顺序',[
 '依次压入1和2，弹出一次，再压入3，最终出栈是1、3吗？',
 '先记录第一次弹出的2。此时栈内只剩1；压入3后，栈顶是3，因此剩余出栈顺序是3、1。栈顶由当前状态决定，不由最初输入顺序决定。',
 '若改成队列，同样先入1和2、出一次、再入3，剩余应是2、3？',
 '正确。队列移除最早进入且尚未离开的元素。可用空结构和只含一个元素的情况再检查操作前提，空栈和空队列都不应直接取元素。'],
 '独立追踪栈与队列的交错操作','逐步记录当前元素和下一次可移除位置，辨别后进先出与先进先出的差别。'),
 ('冒泡排序','一趟结束后究竟确定什么',[
 '冒泡排序第一趟结束，是最小元素已经到开头了吗？',
 '对于从左向右比较相邻元素、逆序时交换的升序写法，第一趟会把最大元素移到末尾。前面部分还不一定有序。可以用[3,1,2]逐次比较验证。',
 '视频里右边界为什么每一趟缩短？',
 '因为末尾已经确定了一个最大值，下一趟无需再次比较它。边界缩短对应“已完成后缀”的不变量；若一整趟没有交换，可以提前结束。'],
 '说明排序边界与已完成区域','用不同输入追踪一趟交换，解释末尾归位、边界收缩和提前结束条件。'),
 ('广度优先搜索','访问标记应放在何时',[
 'BFS使用队列，我在出队时才标记访问可以吗？',
 '若多个节点都指向同一个未出队节点，它可能重复入队。通常在首次入队时标记，表示该节点已经进入待处理集合，之后遇到它就跳过。',
 '图存在环时，这样能避免无限重复吗？',
 '能，已标记节点不会再次入队。还需区分从一个起点可达的部分与整张图；若要遍历不连通图，需要对尚未访问的节点继续发起搜索。'],
 '完成带环图的BFS状态追踪','同时记录队列与访问集合，解释首次入队标记和不连通图的处理。'),
 ('哈希冲突处理','相同哈希值是否覆盖原数据',[
 '两个键的哈希值相同，后来的键是否会覆盖前面的键？',
 '哈希值相同只表示候选位置冲突，系统仍需比较键。链地址法把冲突项放在同一桶的链中；开放寻址则按规则寻找其他位置。',
 '线性探测中删除一个元素，直接把位置标成空闲可以吗？',
 '直接清空可能截断后续键的查找路径。常见做法使用删除标记，查找继续越过它，插入时再按规则复用。请区分“从未使用”与“曾经删除”两种状态。'])]
}


def refine_sample_text(db):
    if not db.execute('SELECT 1 FROM sample_packages WHERE version=5001').fetchone() or db.execute('SELECT 1 FROM sample_packages WHERE version=5002').fetchone():return
    for code,lessons in DIALOGUES.items():
        course=db.execute('SELECT id FROM courses WHERE code=?',(code,)).fetchone()
        if not course:continue
        for i,(topic,title,messages,*goal) in enumerate(lessons):
            node=db.execute('SELECT id FROM knowledge_points WHERE course_id=? AND title=?',(course[0],topic)).fetchone()
            key=lambda part:f'v5:{code}:{part}:{i}'
            entity=db.execute('SELECT entity_id FROM sample_entities WHERE sample_key=?',(key('conversation'),)).fetchone()
            if entity and node:
                conv=db.execute('SELECT * FROM ai_conversations WHERE id=?',(entity[0],)).fetchone()
                rows=db.execute('SELECT m.* FROM ai_messages m JOIN sample_entities e ON e.entity_id=m.id AND e.entity_table=? WHERE m.conversation_id=? ORDER BY m.id',('ai_messages',conv['id'])).fetchall() if conv else []
                old_title=conv['title'].removesuffix('：从例子到边界') if conv else ''
                old_node=db.execute('SELECT * FROM knowledge_points WHERE course_id=? AND title=?',(course[0],old_title)).fetchone()
                original=[f'我理解了定义，但不知道怎样检查{old_title}的边界。', (old_node['description'] if old_node else '')+'\n先把输入和初始状态列出来，每执行一步只改变对应变量。请先预测一个最小输入的结果。','如果输入为空，是否还应该继续执行？','先判断操作的前提。空输入没有可处理元素，需要明确返回空结果或无数据状态；不能用默认的成功值代替。再尝试一个元素，对照循环或函数的终止条件。']
                if old_node and len(rows)==4 and [r['content'] for r in rows]==original and json.loads(conv['context']).get('knowledge_point_id')==old_node['id']:
                    for row,text in zip(rows,messages):db.execute('UPDATE ai_messages SET content=? WHERE id=?',(text,row['id']))
                    context=json.loads(conv['context']);context.update(knowledge_point_id=node[0],sample_version=5002)
                    db.execute('UPDATE ai_conversations SET title=?,context=? WHERE id=?',(title,json.dumps(context,ensure_ascii=False),conv['id']))
            if goal and node:
                entity=db.execute('SELECT entity_id FROM sample_entities WHERE sample_key=?',(key('goal'),)).fetchone()
                if entity:
                    row=db.execute('SELECT * FROM learning_goals WHERE id=?',(entity[0],)).fetchone()
                    old_ids=json.loads(row['knowledge_ids']) if row else []
                    old_node=db.execute('SELECT title FROM knowledge_points WHERE id=?',(old_ids[0],)).fetchone() if len(old_ids)==1 else None
                    if row and old_node and row['title']=='掌握'+old_node[0]+'与边界' and row['description']=='能独立追踪典型例子，并解释新输入的结果。':
                        db.execute('UPDATE learning_goals SET title=?,description=?,knowledge_ids=? WHERE id=?',(goal[0],goal[1],json.dumps([node[0]]),row['id']))
        for i in range(12):
            saved=db.execute("SELECT p.* FROM study_plans p JOIN sample_entities e ON e.entity_id=p.id AND e.entity_table='study_plans' WHERE e.sample_key=?",(f'v5:{code}:plan:{i}',)).fetchone()
            if not saved or saved['description']!='执行后核对边界，记录理解变化。':continue
            point=db.execute('SELECT title,description FROM knowledge_points WHERE id=?',(saved['knowledge_id'],)).fetchone()
            related=db.execute("SELECT id FROM learning_goals WHERE course_id=? AND student_id=? AND knowledge_ids=? LIMIT 1",(course[0],saved['student_id'],json.dumps([saved['knowledge_id']]))).fetchone()
            original_goal=db.execute('SELECT entity_id FROM sample_entities WHERE sample_key=?',(f'v5:{code}:goal:{i%4}',)).fetchone()
            if point:
                db.execute('UPDATE study_plans SET description=? WHERE id=?',(point['description'],saved['id']))
                if original_goal and saved['goal_id']==original_goal[0]:db.execute('UPDATE study_plans SET goal_id=? WHERE id=?',(related[0] if related else None,saved['id']))
    old=db.execute('SELECT seed,time_base FROM sample_packages WHERE version=5001').fetchone()
    db.execute('INSERT INTO sample_packages(version,seed,time_base) VALUES(5002,?,?)',(old[0],old[1]))
