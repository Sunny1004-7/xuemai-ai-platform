"""由课程知识定义注册实验能力，运行时只读取明确映射。"""
import json

ACTIVITIES = {
    '栈与队列': ['stack', 'queue'], '括号匹配': ['stack'], '函数调用栈': ['stack'],
    '循环队列': ['queue'], '队列与层序遍历': ['queue'], '队列应用': ['queue'],
    '冒泡排序': ['sort'], '快速排序': ['sort'], '二叉树': ['tree'], '二叉搜索树': ['tree'],
    '图的遍历': ['bfs'], '广度优先搜索': ['bfs'],
    '循环与条件': ['py-loop', 'py-branch'], '分支边界': ['py-branch'], '布尔表达式': ['py-branch'],
    '累加与循环不变量': ['py-loop'], 'break与continue': ['py-loop'],
    '列表遍历': ['py-list'], '列表切片与别名': ['py-list'],
    '函数定义与返回': ['py-function'], '参数传递': ['py-function'], '作用域': ['py-function'],
}


def register_activities(db):
    for point in db.execute('SELECT id,title FROM knowledge_points'):
        for mode in ACTIVITIES.get(point['title'], []):
            db.execute('INSERT OR IGNORE INTO knowledge_activities(knowledge_id,mode) VALUES(?,?)', (point['id'],mode))


def infer_knowledge(db, request):
    if request.knowledge_point_id:
        return request.knowledge_point_id
    for table, identity in [('questions', request.question_id), ('resources',request.resource_id)]:
        if identity:
            row=db.execute(f'SELECT knowledge_id FROM {table} WHERE id=? AND course_id=?',(identity,request.course_id)).fetchone()
            if row and row[0]:
                return row[0]
    text=request.message
    matches=[]
    for point in db.execute('SELECT id,title FROM knowledge_points WHERE course_id=?',(request.course_id,)):
        if point['title'] in text:
            matches.append((len(point['title']),point['id']))
    if matches:
        return max(matches)[1]
    # 只对已注册的主题词提供确定映射，普通课程问题保持无知识点。
    aliases={'队列':'queue','栈':'stack','排序':'sort','循环':'py-loop','列表':'py-list','函数':'py-function'}
    for token,mode in aliases.items():
        if token in text:
            row=db.execute('SELECT k.id FROM knowledge_points k JOIN knowledge_activities a ON a.knowledge_id=k.id WHERE k.course_id=? AND a.mode=? ORDER BY length(k.title),k.id LIMIT 1',(request.course_id,mode)).fetchone()
            if row:
                return row[0]
    return None


def video_location(resource, knowledge_id, timestamp=None):
    metadata=json.loads(resource['metadata'] or '{}')
    matches=[item for item in metadata.get('timeline',[]) if item.get('knowledge_id')==knowledge_id]
    if timestamp is not None:
        return min(float(metadata.get('duration') or timestamp),timestamp)
    return float(matches[0].get('time',0)) if matches else 0
