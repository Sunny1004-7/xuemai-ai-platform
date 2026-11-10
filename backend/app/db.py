"""SQLite store: foreign keys, explicit migrations and atomic units of work."""
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def database_path():
    path = Path(os.getenv("DATABASE_PATH", "data/xuemai.db"))
    return path if path.is_absolute() else ROOT / path


@contextmanager
def get_db():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA = (Path(__file__).resolve().parents[1] / "migrations" / "001_initial.sql").read_text(encoding="utf-8")


def init_db():
    with get_db() as db:
        db.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        directory=Path(__file__).resolve().parents[1]/"migrations"
        for migration in sorted(directory.glob("*.sql")):
            version=int(migration.name.split("_",1)[0])
            if not db.execute("SELECT 1 FROM schema_migrations WHERE version=?",(version,)).fetchone():
                db.executescript(migration.read_text(encoding="utf-8"))
                db.execute("INSERT INTO schema_migrations(version) VALUES(?)",(version,))
        if not db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            seed(db)
        from .content import upgrade_content
        upgrade_content(db)
        from .demo_cohort import seed_cohort
        seed_cohort(db)
        from .retrieval import sync_index
        sync_index(db)


def seed(db):
    from .auth import hash_password
    password = hash_password("Xuemai123!")
    db.executemany("INSERT INTO users(id,username,name,role,password_hash) VALUES(?,?,?,?,?)", [(1,"teacher","林知远","teacher",password),(2,"student1","陈星河","student",password)])
    db.executemany("INSERT INTO courses(id,title,description,code,color,teacher_id) VALUES(?,?,?,?,?,1)", [(1,"数据结构与算法","从理解结构到设计高效算法，在每次探索中建立自己的知识网络。","CS201","#42685b"),(2,"Python 程序设计","用代码表达想法，从基础语法走向问题求解。","CS101","#6374a4")])
    db.executemany("INSERT INTO classes(id,course_id,name,join_code) VALUES(?,?,?,?)", [(1,1,"计算机科学 2026 级 1 班","XM2026"),(2,2,"Python 探索班","PY2026")])
    db.executemany("INSERT INTO class_members VALUES(?,?)", [(1,2),(2,2)])
    db.executemany("INSERT INTO chapters(id,course_id,title,position) VALUES(?,?,?,?)", [(1,1,"线性结构",1),(2,1,"树与图",2),(3,1,"排序与查找",3),(4,2,"程序基础",1)])
    nodes=[(1,1,1,"数组与链表","数组通过连续空间实现随机访问，链表通过指针连接节点。",30,140),(2,1,1,"栈与队列","栈后进先出，队列先进先出。栈适合回溯，队列适合广度优先搜索。",250,60),(3,1,1,"递归与分治","递归需要终止条件与递归推进；分治将问题拆成独立子问题。",250,240),(4,1,2,"二叉树","每个节点最多两个孩子；前中后序遍历采用不同访问时机。",470,60),(5,1,2,"图的遍历","BFS使用队列按层探索；DFS使用栈或递归深入探索。",690,100),(6,1,3,"冒泡排序","相邻元素比较交换，每一轮将未排序部分最大元素移动到末尾。",470,270),(7,1,3,"快速排序","选定枢轴后划分区间，递归排序；平均 O(n log n)。",690,290),(8,1,3,"二分查找","有序序列上折半缩小查找区间，时间复杂度 O(log n)。",910,200),(9,2,4,"变量与类型","Python变量绑定对象；整数、字符串和列表具有不同语义。",50,100),(10,2,4,"循环与条件","使用条件与循环组织程序控制流。",300,100)]
    db.executemany("INSERT INTO knowledge_points(id,course_id,chapter_id,title,description,x,y) VALUES(?,?,?,?,?,?,?)",nodes)
    db.executemany("INSERT INTO knowledge_edges(course_id,source,target) VALUES(?,?,?)", [(1,1,2),(1,1,3),(1,2,4),(1,2,5),(1,3,6),(1,3,7),(1,6,8),(1,7,8),(2,9,10)])
    for n in nodes:
        db.execute("INSERT INTO resources(course_id,knowledge_id,title,kind,content) VALUES(?,?,?,?,?)", (n[1],n[0],n[3]+"学习讲义","document",n[4]+"\n学习目标：理解定义、手工追踪执行步骤，并使用程序验证。\n合成教学素材，由项目开发时编写。"))
    metadata={"duration":30,"subtitles":[{"start":0,"end":8,"text":"冒泡排序：比较相邻元素，较大的元素向右移动。"},{"start":8,"end":18,"text":"每一轮结束，最大元素确定在未排序部分的末尾。"},{"start":18,"end":30,"text":"最坏比较次数 n(n-1)/2，时间复杂度为 O(n²)。"}],"timeline":[{"time":0,"knowledge_id":6,"title":"相邻比较"},{"time":10,"knowledge_id":6,"title":"交换与一轮结束"},{"time":22,"knowledge_id":6,"title":"复杂度与检查"}],"checkpoints":[{"time":20,"question_id":3}],"checkpoint_question_id":3,"synthetic":True}
    db.execute("INSERT INTO resources(id,course_id,knowledge_id,title,kind,content,url,metadata) VALUES(100,1,6,?,?,?,?,?)",("看见算法：冒泡排序","video","30秒冒泡排序教学演示；相邻比较与交换；最大元素向右移动。","/media/sorting-demo.mp4",json.dumps(metadata,ensure_ascii=False)))
    qs=[(1,1,2,"single","依次将 1、2、3 入栈后，首先出栈的是？",["1","2","3","无法确定"],"3","栈遵循后进先出，最后进入的 3 最先离开。",1,["想象一摞盘子，最后放上的最先拿走。"],{}),(2,1,2,"multiple","以下哪些场景适合使用栈？",["函数调用","括号匹配","按到达顺序排队","撤销操作"],["函数调用","括号匹配","撤销操作"],"函数调用、括号匹配和撤销都需要后进先出。",2,["寻找最近发生、最先处理的场景。"],{}),(3,1,6,"single","冒泡排序完成第一轮后，哪个元素的位置已经确定？",["最小元素","最大元素","中间元素","所有元素"],"最大元素","相邻比较把最大元素逐次交换到末尾。",1,["追踪当前最大的值如何在每次比较中向右移动。"],{}),(4,1,5,"true_false","无权图中，BFS 可以求出从起点到各点的最少边数。",["正确","错误"],"正确","BFS按层扩展；首次访问时的层数就是最少边数。",2,["思考每一层与起点距离的关系。"],{}),(5,1,8,"fill","二分查找要求待查找序列具有哪种性质？",[],"有序","折半排除区间需要单调有序。",1,["如果两侧大小关系不确定，还能排除一半吗？"],{}),(6,1,7,"short","说明快速排序最坏情况出现的原因，并提出一种改进思路。",[],"连续选到极端枢轴；随机化或三数取中","极端枢轴导致子问题规模不均衡，可随机选枢轴降低概率。",3,["关注划分后两侧区间是否均衡。"],{"criteria":[{"name":"解释不均衡划分","points":50},{"name":"提出随机化或合理枢轴","points":50}],"total":100}),(7,1,4,"single","二叉树中序遍历的访问顺序是？",["根左右","左根右","左右根","右根左"],"左根右","中序：先左子树，再根，最后右子树。",1,["中指的是根节点的访问位置。"],{}),(8,1,1,"single","数组按下标访问元素的时间复杂度为？",["O(1)","O(n)","O(log n)","O(n²)"],"O(1)","连续存储可以用基址和偏移计算地址。",1,["地址可以直接计算，不需要逐个遍历。"],{}),(9,2,9,"single","Python 中 type(3) 的结果对应哪种类型？",["int","str","list","bool"],"int","整数常量3的类型是int。",1,["3没有引号。"],{})]
    db.executemany("INSERT INTO questions(id,course_id,knowledge_id,type,title,options,answer,explanation,difficulty,hints,rubric) VALUES(?,?,?,?,?,?,?,?,?,?,?)", [(a,b,c,d,e,json.dumps(f,ensure_ascii=False),json.dumps(g,ensure_ascii=False),h,i,json.dumps(j,ensure_ascii=False),json.dumps(k,ensure_ascii=False)) for a,b,c,d,e,f,g,h,i,j,k in qs])
    db.execute("INSERT INTO assignments(id,course_id,class_id,teacher_id,title,description,question_ids,student_ids,due_at) VALUES(1,1,1,1,?,?,?,?,?)",("线性结构与排序巩固","完成三道练习，检验对栈和排序过程的理解。", "[1,2,3]","[]","2026-11-18T23:59:00"))
    db.execute("INSERT INTO classroom(course_id,title,prompt) VALUES(1,'今天的思考','为什么广度优先搜索需要队列，而不是栈？')")


def as_dict(row):
    return dict(row) if row else None


def json_fields(row, fields):
    item = dict(row)
    for field in fields:
        if field in item and isinstance(item[field], str):
            item[field] = json.loads(item[field])
    return item


if __name__ == "__main__":
    init_db()
    print("数据库初始化完成（合成演示数据）")
