"""自编课程内容的幂等扩充。按标题匹配，自定义节点与历史记录保留。"""
import json

# 标题、主题、定义、例子、检测问题、选项、答案、技能、难度、先修。
NODES = [
    ('数组与链表', 0, '数组连续存储并支持常数时间下标访问；链表通过链接组织节点。', '在 [4,7,9] 的下标1处插入5，数组要移动7和9，链表在已知前驱时只改链接。', '已知单链表前驱时，插入新节点主要修改什么？', ['链接', '所有后续元素值', '数组容量'], '链接', 'concept', 1, []),
    ('栈与队列', 0, '栈后进先出；队列先进先出。两者的限制操作决定应用场景。', '输入1、2、3，全部入栈后依次弹出3、2、1；全部入队后依次取出1、2、3。', '1、2、3依次入队，首先出队的是？', ['1', '2', '3'], '1', 'procedure', 1, ['数组与链表']),
    ('递归与分治', 1, '递归把问题转成更小的同类问题；分治还需要分解、求解和合并。', '求长度4的数组和，可分成两个长度2的区间，再把两个部分和相加。', '分治中子问题求解后通常还需执行哪一步？', ['合并', '忽略结果', '无限递归'], '合并', 'reasoning', 2, ['递归终止条件']),
    ('二叉树', 2, '二叉树每个节点最多有两个孩子，左右子树位置有区别。', '根A的左孩子B、右孩子C，对应中序B A C，前序A B C。', '二叉树中一个节点最多有几个孩子？', ['2', '1', '3'], '2', 'concept', 1, ['递归终止条件']),
    ('图的遍历', 3, '遍历需记录已访问节点，避免在环中重复访问。DFS深入，BFS逐层。', '图A-B、A-C、B-D，从A按字母顺序BFS访问A B C D。', '图中有环时，避免重复处理节点需要什么？', ['访问标记', '仅排序编号', '删除所有边'], '访问标记', 'reasoning', 2, ['邻接表与邻接矩阵', '栈与队列']),
    ('冒泡排序', 4, '从左到右相邻比较交换，一轮结束使当前最大值就位。', '[3,1,2] 经比较3与1变[1,3,2]，再比较3与2变[1,2,3]。', '若一轮没有发生交换，可以做什么？', ['提前结束', '必须无限继续', '逆序整个数组'], '提前结束', 'procedure', 1, ['数组与链表']),
    ('快速排序', 4, '按枢轴划分区间，再递归处理两侧；最坏不均衡划分为二次复杂度。', '[4,1,3,2] 以2为枢轴，左侧1，右侧4与3，再分别处理。', '连续极端枢轴导致哪种划分？', ['两侧严重不均衡', '每次等长', '没有递归'], '两侧严重不均衡', 'reasoning', 3, ['递归与分治']),
    ('二分查找', 5, '有序随机访问序列可通过中点比较折半排除区间。', '[2,5,8,11,14] 找11，先看8，更新左边界为3，再在右半区间查找。', '闭区间二分中若目标大于中点值，左边界如何变？', ['mid+1', 'mid-1', '保持不变'], 'mid+1', 'procedure', 2, ['数组与链表', '时间复杂度']),
    ('顺序表插入与删除', 0, '顺序表保持元素连续，插入和删除通常需要移动后续元素。', '[1,3,5] 在开头插入0，需要移动3个已有元素。', '长度n顺序表在首部插入的最坏时间复杂度是？', ['O(n)', 'O(1)', 'O(log n)'], 'O(n)', 'transfer', 2, ['数组与链表', '时间复杂度']),
    ('单链表链接操作', 0, '先连接新节点到后继，再将前驱指向新节点，避免丢失链。', '在p后插入s：s.next=p.next，然后p.next=s。', '在p后插入s，首先执行哪条语句？', ['s.next=p.next', 'p.next=s', 'p=None'], 's.next=p.next', 'procedure', 2, ['数组与链表']),
    ('双向链表', 0, '双向链表维护前驱和后继，插入与删除必须同时保持两个方向一致。', '删除中间节点p需将p.prev.next接到p.next，并将p.next.prev接到p.prev。', '双向链表删除中间节点时要维护几个方向？', ['两个方向', '仅后继', '无需改链接'], '两个方向', 'procedure', 2, ['单链表链接操作']),
    ('循环队列', 0, '循环队列用取模实现下标回绕，常用牺牲一个位置区分空满。', '容量5、保留一空位时，front=2、rear=1表示4个有效元素，队列已满。', '保留一空位的容量N循环队列，满条件为？', ['(rear+1)%N==front', 'rear==front', 'rear==N'], '(rear+1)%N==front', 'procedure', 2, ['栈与队列']),
    ('括号匹配', 0, '左括号入栈，右括号必须与栈顶配对；结束时栈为空才匹配。', '([)] 到右圆括号时栈顶是左方括号，因此立刻判定不匹配。', '序列([)]是否匹配？', ['不匹配', '匹配', '只数数量即可'], '不匹配', 'transfer', 3, ['栈与队列']),
    ('时间复杂度', 1, '关注输入规模增长时基本操作次数的阶，忽略常数倍与低阶项。', '3n²+2n+1随n增长由n²项主导，其渐近上界为O(n²)。', '3n²+2n+1的常用紧阶表达为？', ['Θ(n²)', 'Θ(n)', 'Θ(1)'], 'Θ(n²)', 'reasoning', 1, []),
    ('空间复杂度', 1, '额外空间随输入规模的增长量，包括辅助结构和递归调用栈。', '递归深度n且每层使用常数额外空间时，栈空间为O(n)。', '深度n的递归调用栈占用空间通常为？', ['O(n)', 'O(1)', 'O(n²)'], 'O(n)', 'reasoning', 2, ['时间复杂度']),
    ('递归终止条件', 1, '递归必须有可到达的基础情况，且每次调用朝基础情况缩小问题。', 'factorial(n)在n=0返回1，n>0调用n*factorial(n-1)。', '阶乘递归中n每次减1的作用是什么？', ['朝终止条件推进', '增加无限调用', '省去基础情况'], '朝终止条件推进', 'reasoning', 1, []),
    ('二叉树遍历', 2, '前序根左右，中序左根右，后序左右根；层序使用队列。', '根A、左B、右C，后序为B C A。', '根A、左B、右C的后序结果为？', ['B C A', 'A B C', 'B A C'], 'B C A', 'procedure', 2, ['二叉树', '栈与队列']),
    ('二叉搜索树', 2, '对无重复键的搜索树，左子树键小于根，右子树键大于根。', '依次插入5、2、8、3，3位于2的右侧；中序得到2、3、5、8。', '无重复键二叉搜索树的中序结果是什么顺序？', ['严格递增', '严格递减', '任意顺序'], '严格递增', 'reasoning', 2, ['二叉树遍历']),
    ('堆与堆调整', 2, '小根堆是完全二叉树，每个父节点不大于孩子；只有堆顶保证全局最小。', '[1,4,2,8,5] 是小根堆，但数组整体并不有序。', '小根堆一定能直接确定哪个元素？', ['最小值', '所有元素有序位置', '中位数'], '最小值', 'concept', 2, ['二叉树']),
    ('优先队列', 2, '优先队列按优先级而非到达次序取出元素，二叉堆可实现对数时间插入与弹出。', '急诊任务优先级1、3、2，约定数字越小越紧急，则依次处理1、2、3。', '二叉堆实现的优先队列插入复杂度为？', ['O(log n)', 'O(n²)', 'O(1)且无调整'], 'O(log n)', 'transfer', 3, ['堆与堆调整', '时间复杂度']),
    ('邻接表与邻接矩阵', 3, '邻接矩阵使用V²空间；邻接表使用O(V+E)空间，常用于稀疏图。', '1000个节点、2000条边的图，用邻接表可避免保存百万个矩阵位置。', '稀疏图通常更适合哪种存储？', ['邻接表', '完整V²矩阵总是更省', '无需存边'], '邻接表', 'reasoning', 1, ['数组与链表']),
    ('深度优先搜索', 3, 'DFS沿一条路径深入，遇到已访问或无可行后继时回退。', 'A邻居B、C，B邻居D，按字母次序DFS得到A B D C。', 'DFS的显式实现通常使用什么？', ['栈', '仅FIFO队列', '计数器即可'], '栈', 'procedure', 2, ['图的遍历', '递归终止条件']),
    ('广度优先搜索', 3, 'BFS以队列按层扩展，无权图中首次到达的层数为最少边数。', 'A连接B和C，B连接D，A到D的最少边数为2。', '无权图最少边数路径可以用什么求解？', ['BFS', '冒泡排序', '二分查找'], 'BFS', 'transfer', 3, ['图的遍历']),
    ('拓扑排序', 3, '有向无环图可将所有先修节点排在后续节点前；Kahn算法反复取入度零节点。', 'A→C、B→C，A B C与B A C均为合法顺序。', 'Kahn算法优先取出哪类节点？', ['入度为0', '出度最大', '编号最大'], '入度为0', 'procedure', 3, ['邻接表与邻接矩阵', '栈与队列']),
    ('插入排序', 4, '把当前元素插入已排好序的前缀，后移较大元素。', '[3,1,2] 先将1插到3前，再将2插入1和3之间。', '插入排序每轮扩展的是哪个部分？', ['有序前缀', '随机后缀', '单个最大值位置'], '有序前缀', 'procedure', 1, ['顺序表插入与删除']),
    ('归并排序', 4, '递归分半排序，再用线性时间合并两个有序子序列。', '[1,4]和[2,3]归并：依次取1、2、3、4。', '两个总长n的有序序列归并耗时为？', ['O(n)', 'O(n²)', 'O(1)'], 'O(n)', 'reasoning', 2, ['递归与分治']),
    ('排序稳定性', 4, '相等键在排序后保持原相对顺序称为稳定；实现中的相等处理影响稳定性。', '分数相同的甲、乙原来甲在前，稳定排序仍保持甲在乙之前。', '归并时相等键先取左侧能维护什么？', ['稳定性', '逆序性', '枢轴随机性'], '稳定性', 'transfer', 3, ['归并排序', '插入排序']),
    ('顺序查找', 5, '逐个检查元素直到命中或结束，无需有序，最坏比较n次。', '[9,4,7]找7需比较3次；找2也要检查整个序列。', '无序数组顺序查找最坏比较次数为？', ['n', 'log₂n', '1'], 'n', 'concept', 1, ['数组与链表']),
    ('哈希表', 5, '哈希函数把键映射到桶，平均效率依赖分布与负载，最坏不保证常数时间。', 'h(k)=k mod 5时，7映射到桶2，12也映射到桶2。', 'h(k)=k mod 5时，12映射到哪个桶？', ['2', '5', '12'], '2', 'procedure', 2, ['数组与链表']),
    ('哈希冲突处理', 5, '不同键映射同桶称冲突，可用链地址或开放寻址处理，不能直接覆盖已有键。', 'h(k)=k mod 5，7和12冲突，可在桶2维护链7→12。', '两个不同键哈希到同一桶时应该怎样？', ['保留两键并处理冲突', '直接覆盖旧键', '认定两键相同'], '保留两键并处理冲突', 'transfer', 3, ['哈希表', '单链表链接操作']),
]
GROUPS = ['线性结构', '递归与复杂度', '树结构', '图结构', '排序方法', '查找与索引']


def upgrade_content(db):
    upgrade_media(db)
    revision = 2
    if db.execute('SELECT 1 FROM content_revisions WHERE version=?', (revision,)).fetchone():
        return
    course = db.execute("SELECT id FROM courses WHERE code='CS201'").fetchone()
    if not course:
        return
    cid = course['id']
    chapters = []
    # 复用旧章节，避免留下空章节。
    aliases = {2: '树与图', 4: '排序与查找'}
    for position, title in enumerate(GROUPS):
        row = db.execute('SELECT id FROM chapters WHERE course_id=? AND title IN (?,?) ORDER BY id LIMIT 1', (cid, title, aliases.get(position, title))).fetchone()
        if row:
            chapter_id = row['id']
            db.execute('UPDATE chapters SET title=?,position=? WHERE id=?', (title, position+1, chapter_id))
        else:
            chapter_id = db.execute('INSERT INTO chapters(course_id,title,position) VALUES(?,?,?)', (cid, title, position+1)).lastrowid
        chapters.append(chapter_id)
    mapping = {}
    for title, group, definition, example, prompt, options, answer, skill, difficulty, prereqs in NODES:
        old = db.execute('SELECT id FROM knowledge_points WHERE course_id=? AND title=?', (cid, title)).fetchone()
        if old:
            kid = old['id']
            db.execute('UPDATE knowledge_points SET chapter_id=?,difficulty=?,description=? WHERE id=?', (chapters[group], difficulty, definition, kid))
        else:
            kid = db.execute('INSERT INTO knowledge_points(course_id,chapter_id,title,description,difficulty) VALUES(?,?,?,?,?)', (cid, chapters[group], title, definition, difficulty)).lastrowid
        mapping[title] = kid
        content = f'# {title}\n\n{definition}\n\n## 例子\n{example}\n\n## 操作检查\n先写出初始状态，再逐步说明每次操作改变了什么。比较正常输入、空输入与边界输入，检查结构约束是否保持。\n\n## 自测\n{prompt}\n完成练习后，尝试更换输入解释同一条规则。'
        resource = db.execute("SELECT id FROM resources WHERE knowledge_id=? AND title=? AND kind='document'", (kid, title+'学习讲义')).fetchone()
        if resource:
            db.execute('UPDATE resources SET content=?,version=version+1 WHERE id=?', (content, resource['id']))
        else:
            db.execute("INSERT INTO resources(course_id,knowledge_id,title,kind,content) VALUES(?,?,?,'document',?)", (cid, kid, title+'学习讲义', content))
        if not db.execute('SELECT 1 FROM questions WHERE knowledge_id=? AND title=?', (kid, prompt)).fetchone():
            diagnosis = {o: ('程序步骤偏差' if skill == 'procedure' else '概念辨析待巩固' if skill == 'concept' else '推理依据不足' if skill == 'reasoning' else '迁移应用待检验') for o in options if o != answer}
            db.execute("INSERT INTO questions(course_id,knowledge_id,type,title,options,answer,explanation,difficulty,hints,skill,diagnostic_map) VALUES(?,?,'single',?,?,?,?,?,?,?,?)", (cid, kid, prompt, json.dumps(options, ensure_ascii=False), json.dumps(answer, ensure_ascii=False), definition+' '+example, difficulty, json.dumps(['先追踪例子中的状态变化，再判断选项。'], ensure_ascii=False), skill, json.dumps(diagnosis, ensure_ascii=False)))
    # 仅校正自带旧版的不准确先修边；保留其他人为扩充关系。
    for a,b in [('冒泡排序','二分查找'),('快速排序','二分查找'),('递归与分治','冒泡排序'),('栈与队列','二叉树'),('数组与链表','递归与分治')]:
        db.execute('DELETE FROM knowledge_edges WHERE course_id=? AND source=? AND target=?', (cid, mapping[a], mapping[b]))
    for spec in NODES:
        for prerequisite in spec[-1]:
            db.execute('INSERT OR IGNORE INTO knowledge_edges(course_id,source,target) VALUES(?,?,?)', (cid, mapping[prerequisite], mapping[spec[0]]))
    db.execute("UPDATE questions SET skill='procedure',diagnostic_map=? WHERE id=1", (json.dumps({'1':'入栈与出栈顺序混淆','2':'程序步骤偏差'}, ensure_ascii=False),))
    db.execute("UPDATE questions SET skill='procedure' WHERE id IN (3,7)")
    db.execute("UPDATE questions SET skill='reasoning' WHERE id IN (4,6)")
    db.execute("UPDATE resources SET metadata=json_set(metadata,'$.duration',36,'$.subtitles[2].end',36),content='36秒冒泡排序过程：相邻比较、交换与边界收缩。' WHERE id=100 AND url='/media/sorting-demo.mp4'")
    db.execute('INSERT INTO content_revisions(version) VALUES(?)', (revision,))
    if not db.execute('SELECT 1 FROM attempts LIMIT 1').fetchone():
        seed_learning_journey(db)


def seed_learning_journey(db):
    """单个合成学生的连续真实接口逻辑作答，清楚保留合成来源。"""
    from .learning import record_attempt
    user = dict(db.execute("SELECT * FROM users WHERE username='student1'").fetchone())
    for qid, answer, hints in [(8,'O(1)',0),(1,'1',0),(3,'最大元素',0),(1,'3',1),(4,'错误',0),(5,'有序',0)]:
        question = db.execute('SELECT * FROM questions WHERE id=?', (qid,)).fetchone()
        result = record_attempt(db, user, question, answer, hints)
        db.execute("UPDATE learning_events SET payload=json_set(payload,'$.synthetic',json('true')) WHERE json_extract(payload,'$.attempt_id')=?", (result['id'],))


def upgrade_media(db):
    from pathlib import Path
    path=Path(__file__).resolve().parents[1]/'media/teaching-metadata.json'
    if not path.is_file() or db.execute('SELECT 1 FROM content_revisions WHERE version=3').fetchone():
        return
    course=db.execute("SELECT id FROM courses WHERE code='CS201'").fetchone()
    if not course:return
    for item in json.loads(path.read_text(encoding='utf-8')):
        url='/media/'+item['slug']+'.mp4'
        old=db.execute('SELECT * FROM resources WHERE course_id=? AND url=?',(course['id'],url)).fetchone()
        title='看见算法：'+item['title']
        content='\n'.join(s['text'] for s in item['subtitles'])
        if old:
            db.execute('INSERT INTO resource_versions(resource_id,version,content,metadata) VALUES(?,?,?,?)',(old['id'],old['version'],old['content'],old['metadata']))
            db.execute('UPDATE resources SET title=?,content=?,metadata=?,version=version+1 WHERE id=?',(title,content,json.dumps(item,ensure_ascii=False),old['id']))
        else:
            db.execute("INSERT INTO resources(course_id,knowledge_id,title,kind,content,url,metadata) VALUES(?,?,?,'video',?,?,?)",(course['id'],item['knowledge_id'],title,content,url,json.dumps(item,ensure_ascii=False)))
    db.execute('INSERT INTO content_revisions(version) VALUES(3)')


def upgrade_round3_content(db):
    if db.execute('SELECT 1 FROM content_revisions WHERE version=3000').fetchone():
        return
    chapter=db.execute("SELECT id,course_id FROM chapters WHERE title='递归与复杂度' AND course_id=1").fetchone()
    if not chapter:
        return
    title='循环边界与不变量'
    point=db.execute('SELECT id FROM knowledge_points WHERE course_id=1 AND title=?',(title,)).fetchone()
    kid=point[0] if point else db.execute("INSERT INTO knowledge_points(course_id,chapter_id,title,description,difficulty,objectives) VALUES(1,?,?,?,2,?)",(chapter[0],title,'循环不变量在循环开始前成立，并由每轮操作保持；结合退出条件解释结果。',json.dumps(['写出循环开始时成立的条件','检查一次迭代是否保持不变量','用退出边界说明结果'],ensure_ascii=False))).lastrowid
    content='# 循环边界与不变量\n\n循环不变量描述每轮开始或结束时始终成立的性质。验证时分为初始化、保持和终止三步。\n\n## 例子\n冒泡排序中，一轮结束后，未排序区间最大值移动到其末尾；外层循环的不变量是右侧后缀已经有序且处于最终位置。若把内层上界多写一位，访问相邻元素时就可能越界。\n\n## 操作检查\n用输入[3,1,2]追踪一次外层循环，标出已排序后缀，并解释下一轮为什么可以缩短边界。'
    if not db.execute("SELECT 1 FROM resources WHERE knowledge_id=? AND kind='document'",(kid,)).fetchone():
        db.execute("INSERT INTO resources(course_id,knowledge_id,title,kind,content) VALUES(1,?,?,'document',?)",(kid,title+'学习讲义',content))
    if not db.execute('SELECT 1 FROM questions WHERE knowledge_id=?',(kid,)).fetchone():
        db.execute("INSERT INTO questions(course_id,knowledge_id,type,title,options,answer,explanation,difficulty,hints,skill,diagnostic_map) VALUES(1,?,'single',?,?,?,?,2,?,'reasoning',?)",(kid,'证明循环不变量时，除初始化和保持外还需要结合什么？',json.dumps(['终止条件','变量名称','界面颜色'],ensure_ascii=False),json.dumps('终止条件',ensure_ascii=False),'退出时的不变量与终止条件共同说明算法结果。',json.dumps(['考虑循环结束时能得出什么。'],ensure_ascii=False),json.dumps({'变量名称':'推理依据不足','界面颜色':'概念辨析待巩固'},ensure_ascii=False)))
    source=db.execute("SELECT id FROM knowledge_points WHERE course_id=1 AND title='数组与链表'").fetchone()
    target=db.execute("SELECT id FROM knowledge_points WHERE course_id=1 AND title='冒泡排序'").fetchone()
    for a,b in [(source[0],kid),(kid,target[0])]:
        db.execute('INSERT OR IGNORE INTO knowledge_edges(course_id,source,target) VALUES(1,?,?)',(a,b))
    db.execute('INSERT INTO content_revisions(version) VALUES(3000)')
