"""段落级联合召回，知识关系增强排序与文档多样性约束。"""
import json
import re


def search_tokens(text):
    stop = {'什么','怎么','如何','为何','是否','可以','应该','学习','当前','解释','说明','一下','哪种','区别','不同','请问','关于','需要','进行','一个','这些','哪些','知识','课程'}
    tokens = re.findall(r'[a-zA-Z0-9_]{2,}|[栈树图堆]', text.lower())
    for run in re.findall(r'[\u4e00-\u9fff]+', text):
        tokens.extend(run[i:i+2] for i in range(len(run)-1) if run[i:i+2] not in stop)
    return list(dict.fromkeys(tokens))


def paragraph_chunks(text):
    heading = ''
    result = []
    for index, paragraph in enumerate(re.split(r'\n\s*\n|(?=^#{1,4} )', text, flags=re.M)):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if paragraph.startswith('#'):
            heading = paragraph.split('\n',1)[0].lstrip('# ').strip()
        for offset in range(0, len(paragraph), 800):
            result.append((f'{heading + " · " if heading else ""}段落{index + 1}' + (f'·片段{offset // 800 + 1}' if len(paragraph)>800 else ''), paragraph[offset:offset+800]))
    return result


def sync_index(db):
    dirty = [row[0] for row in db.execute('SELECT resource_id FROM resource_index_queue')]
    for rid in dirty:
        db.execute('DELETE FROM ai_resource_fts WHERE resource_id=?', (rid,))
        db.execute('DELETE FROM ai_resource_passages WHERE resource_id=?', (rid,))
        resource = db.execute('SELECT * FROM resources WHERE id=?', (rid,)).fetchone()
        if resource:
            for index, (locator, excerpt) in enumerate(paragraph_chunks(resource['content'] or resource['title'])):
                cursor=db.execute('INSERT INTO ai_resource_passages(resource_id,version,locator,ordinal,content) VALUES(?,?,?,?,?)', (rid,resource['version'],locator,index,excerpt))
                db.execute('INSERT INTO ai_resource_fts(rowid,resource_id,course_id,title,excerpt,tokens) VALUES(?,?,?,?,?,?)',
                    (cursor.lastrowid,rid,resource['course_id'],resource['title'],excerpt,' '.join(search_tokens(resource['title']+' '+excerpt))))
        db.execute('DELETE FROM resource_index_queue WHERE resource_id=?', (rid,))
    return len(dirty)


def visible_resource(resource, role):
    metadata = json.loads(resource['metadata'] or '{}')
    return role == 'teacher' or (metadata.get('visibility') != 'teacher' and metadata.get('status') not in {'draft','unpublished'} and metadata.get('published') is not False)


def retrieve(db, course_id, query, knowledge_id=None, *, user=None, conversation_id=None, attachment_ids=(), knowledge_boost=True):
    sync_index(db)
    terms = search_tokens(query)[:40]
    candidate_ids = []
    if terms:
        expression = ' OR '.join('"'+token+'"' for token in terms)
        candidate_ids = [row[0] for row in db.execute('SELECT rowid FROM ai_resource_fts WHERE ai_resource_fts MATCH ? AND course_id=? ORDER BY bm25(ai_resource_fts) LIMIT 28', (expression,course_id))]
    neighbors = set()
    if knowledge_id:
        neighbors={row[0] for row in db.execute('SELECT source FROM knowledge_edges WHERE course_id=? AND target=? UNION SELECT target FROM knowledge_edges WHERE course_id=? AND source=?',(course_id,knowledge_id,course_id,knowledge_id))}
        candidate_ids += [row[0] for row in db.execute('SELECT p.id FROM ai_resource_passages p JOIN resources r ON r.id=p.resource_id WHERE r.course_id=? AND r.knowledge_id=? LIMIT 12',(course_id,knowledge_id))]
    ranked = []
    role = user['role'] if user else 'student'
    for passage_id in dict.fromkeys(candidate_ids):
        row = db.execute('SELECT p.*,r.title,r.knowledge_id,r.metadata FROM ai_resource_passages p JOIN resources r ON r.id=p.resource_id WHERE p.id=? AND r.course_id=?',(passage_id,course_id)).fetchone()
        if not row or not visible_resource(row,role):
            continue
        overlap = len(set(terms) & set(search_tokens(row['title']+' '+row['content']))) / max(1,len(terms))
        association = (.5 if row['knowledge_id']==knowledge_id else .2 if row['knowledge_id'] in neighbors else 0) if knowledge_boost else 0
        ranked.append((overlap + association, {'resource_id':row['resource_id'],'passage_id':row['id'],'title':row['title'],'excerpt':row['content'],'locator':row['locator'],'version':row['version'],
            'url':f"/resources?course={course_id}&resource={row['resource_id']}&passage={row['id']}&version={row['version']}", 'source_kind':'course'}))
    if user:
        for attachment_id in attachment_ids:
            attachment = db.execute('SELECT * FROM ai_attachments WHERE id=? AND user_id=? AND course_id=? AND deleted_at IS NULL',(attachment_id,user['id'],course_id)).fetchone()
            if not attachment or attachment['conversation_id'] not in (None,conversation_id):
                continue
            for chunk in db.execute('SELECT * FROM ai_attachment_chunks WHERE attachment_id=?',(attachment_id,)):
                overlap=len(set(terms)&set(search_tokens(chunk['content']))) / max(1,len(terms))
                ranked.append((overlap+.15, {'attachment_id':attachment_id,'passage_id':chunk['id'],'title':attachment['filename'],'excerpt':chunk['content'],'locator':chunk['locator'],'version':attachment['sha256'][:12],
                    'url':f"/ai/attachments/{attachment_id}?chunk={chunk['id']}",'source_kind':'attachment'}))
    citations=[]
    per_document={}
    remaining=5200
    for score, item in sorted(ranked,key=lambda item: -item[0]):
        if score <= 0:
            continue
        key=(item['source_kind'],item.get('resource_id') or item.get('attachment_id'))
        if per_document.get(key,0)>=2 or len(item['excerpt'])>remaining:
            continue
        per_document[key]=per_document.get(key,0)+1
        remaining-=len(item['excerpt'])
        citations.append({'id':len(citations)+1,'score':round(score,4),**item})
        if len(citations)==5:
            break
    return citations


def citation_support(content, citations):
    checks=[]
    for number in sorted(set(int(value) for value in re.findall(r'\[(\d+)\]',content))):
        if not 1<=number<=len(citations):
            checks.append({'id':number,'supported':False,'reason':'引用编号不存在'})
            continue
        source=citations[number-1]
        sentence=next((part for part in re.split(r'[。！？\n]',content) if f'[{number}]' in part),'')
        common=set(search_tokens(sentence))&set(search_tokens(source['title']+' '+source['excerpt']))
        checks.append({'id':number,'supported':bool(common),'matched_terms':sorted(common)[:8],'locator':source.get('locator','')})
    return checks
