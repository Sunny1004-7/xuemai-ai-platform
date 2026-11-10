"""资源触发器只标记变化；事务内仅重建变化资源的文本片段。"""
import re


def search_tokens(text):
    stop = {'什么','怎么','如何','为何','是否','可以','应该','学习','当前','解释','说明',
            '一下','哪种','区别','不同','请问','关于','需要','进行','一个','这些','哪些','知识','课程'}
    tokens = re.findall(r'[a-zA-Z0-9_]{2,}|[栈树图堆]', text.lower())
    for run in re.findall(r'[\u4e00-\u9fff]+', text):
        tokens.extend(run[i:i+2] for i in range(len(run)-1) if run[i:i+2] not in stop)
    return list(dict.fromkeys(tokens))


def sync_index(db):
    dirty = [r[0] for r in db.execute('SELECT resource_id FROM resource_index_queue')]
    for rid in dirty:
        db.execute('DELETE FROM ai_resource_fts WHERE resource_id=?', (rid,))
        resource = db.execute('SELECT * FROM resources WHERE id=?', (rid,)).fetchone()
        if resource:
            content = resource['content'] or resource['title']
            for start in range(0, len(content), 520):
                excerpt = content[start:start+600]
                db.execute('INSERT INTO ai_resource_fts(resource_id,course_id,title,excerpt,tokens) VALUES(?,?,?,?,?)',
                           (rid, resource['course_id'], resource['title'], excerpt, ' '.join(search_tokens(resource['title']+' '+excerpt))))
        db.execute('DELETE FROM resource_index_queue WHERE resource_id=?', (rid,))
    return len(dirty)


def retrieve(db, course_id, query, knowledge_id=None):
    sync_index(db)
    terms = search_tokens(query)[:32]
    rows = []
    if terms:
        expression = ' OR '.join('"'+token+'"' for token in terms)
        rows = db.execute('SELECT resource_id,title,excerpt FROM ai_resource_fts WHERE ai_resource_fts MATCH ? AND course_id=? ORDER BY bm25(ai_resource_fts) LIMIT 4', (expression, course_id)).fetchall()
    if not rows and knowledge_id:
        rows = db.execute('SELECT id resource_id,title,substr(content,1,600) excerpt FROM resources WHERE course_id=? AND knowledge_id=? AND length(content)>0 ORDER BY id LIMIT 2', (course_id, knowledge_id)).fetchall()
    citations = []
    seen = set()
    for row in rows:
        rid = row['resource_id']
        if rid in seen:
            continue
        seen.add(rid)
        version = db.execute('SELECT version FROM resources WHERE id=?', (rid,)).fetchone()
        if version:
            citations.append({'id': len(citations)+1, 'resource_id': rid, 'title': row['title'], 'excerpt': row['excerpt'],
                              'version': version[0], 'url': f'/resources?course={course_id}&resource={rid}'})
    return citations[:3]
