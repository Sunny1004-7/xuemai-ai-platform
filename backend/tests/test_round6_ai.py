import io
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db import get_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'round6.db'))
    monkeypatch.setenv('AI_MODE','mock')
    monkeypatch.setenv('AI_REQUESTS_PER_MINUTE','30')
    monkeypatch.setenv('XUEMAI_DEMO_COHORT','1')
    with TestClient(app) as client:
        yield client


def headers(client, username='student1'):
    response=client.post('/api/auth/login',json={'username':username,'password':'Xuemai123!'})
    return {'Authorization':'Bearer '+response.json()['token']}


def test_legacy_fts_upgrade_rebuilds_without_losing_content(client):
    from backend.app.db import init_db
    with get_db() as db:
        resources=db.execute('SELECT count(*) FROM resources').fetchone()[0]
        messages=db.execute('SELECT count(*) FROM ai_messages').fetchone()[0]
        db.execute('DELETE FROM schema_migrations WHERE version>=10')
        db.execute('DELETE FROM ai_resource_passages')
        db.execute('DELETE FROM ai_resource_fts')
        db.execute("INSERT INTO ai_resource_fts(rowid,resource_id,course_id,title,excerpt,tokens) VALUES(1,2,1,'旧资源索引','旧片段','旧 片段')")
    init_db()
    init_db()
    with get_db() as db:
        assert db.execute('SELECT count(*) FROM resources').fetchone()[0]==resources
        assert db.execute('SELECT count(*) FROM ai_messages').fetchone()[0]==messages
        assert db.execute('SELECT count(*) FROM ai_resource_passages').fetchone()[0]>resources
        assert db.execute('SELECT count(*) FROM ai_resource_fts').fetchone()[0]==db.execute('SELECT count(*) FROM ai_resource_passages').fetchone()[0]
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def test_initialization_failure_keeps_migration_versions_atomic(tmp_path, monkeypatch):
    from backend.app.db import init_db
    from backend.app import retrieval
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'restart.db'))
    monkeypatch.setenv('AI_MODE','mock')
    original=retrieval.sync_index
    def fail_index(db):
        raise RuntimeError('模拟派生索引初始化中断')
    monkeypatch.setattr(retrieval,'sync_index',fail_index)
    with pytest.raises(RuntimeError,match='初始化中断'):
        init_db()
    with get_db() as db:
        assert db.execute('SELECT max(version) FROM schema_migrations').fetchone()[0]==11
    monkeypatch.setattr(retrieval,'sync_index',original)
    init_db()
    with get_db() as db:
        assert db.execute('SELECT count(*) FROM resources').fetchone()[0]>0
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def events(response):
    assert response.status_code==200,response.text
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]


def test_request_models_and_message_history(client):
    student=headers(client)
    assert {model['id'] for model in client.get('/api/ai/models',headers=student).json()['models']}=={'deepseek-flash','deepseek-v4-pro'}
    for model in ['deepseek-flash','deepseek-v4-pro']:
        response=events(client.post('/api/ai/chat',headers=student,json={'course_id':1,'message':'解释栈的应用','model':model}))
        assert response[0]['model']==model
        conversation=client.get(f"/api/ai/conversations/{response[0]['conversation_id']}",headers=student).json()
        assert conversation['messages'][-1]['model']==model
        assert conversation['messages'][-1]['status']=='complete'
    assert client.post('/api/ai/chat',headers=student,json={'course_id':1,'message':'问题','model':'unlisted'}).status_code==422


def test_attachment_scope_retrieval_deletion_and_history(client):
    student=headers(client)
    teacher=headers(client,'teacher')
    response=client.post('/api/ai/attachments',headers=student,data={'course_id':1},files={'file':('队列笔记.md','队列在层序遍历中保持先进先出，先入队的节点先处理。'.encode(),'text/markdown')})
    assert response.status_code==201,response.text
    attachment=response.json()
    assert client.get('/api/ai/attachments/'+attachment['id'],headers=teacher).status_code==404
    values=events(client.post('/api/ai/chat',headers=student,json={'course_id':1,'message':'根据笔记解释队列层序遍历','attachment_ids':[attachment['id']]}))
    assert any(item.get('attachment_id')==attachment['id'] and item['locator'] for item in values[0]['citations'])
    conversation_id=values[0]['conversation_id']
    detail=client.get(f'/api/ai/conversations/{conversation_id}',headers=student).json()
    assert detail['messages'][0]['attachments'][0]['id']==attachment['id']
    denied=client.post('/api/ai/chat',headers=student,json={'course_id':2,'message':'队列','attachment_ids':[attachment['id']]})
    assert denied.status_code==404
    assert client.post('/api/ai/chat',headers=student,json={'course_id':1,'message':'新会话','attachment_ids':[attachment['id']]}).status_code==404
    assert client.delete('/api/ai/attachments/'+attachment['id'],headers=student).status_code==200
    assert client.get('/api/ai/attachments/'+attachment['id'],headers=student).status_code==404
    with get_db() as db:
        assert db.execute('SELECT COUNT(*) FROM ai_attachment_chunks WHERE attachment_id=?',(attachment['id'],)).fetchone()[0]==0


def test_document_formats_and_image_capability(client):
    from PIL import Image
    from docx import Document
    from pypdf import PdfWriter
    student=headers(client)
    word=io.BytesIO()
    document=Document(); document.add_paragraph('队列测试资料'); document.save(word)
    image=io.BytesIO(); Image.new('RGB',(100,100),'white').save(image,format='PNG')
    for filename,content in [('笔记.txt','栈'.encode()),('成绩.csv','姓名,成绩\n示例,80'.encode()),('教案.docx',word.getvalue())]:
        response=client.post('/api/ai/attachments',headers=student,data={'course_id':1},files={'file':(filename,content)})
        assert response.status_code==201,response.text
        detail=client.get('/api/ai/attachments/'+response.json()['id'],headers=student).json()
        assert detail['chunks'] and detail['chunks'][0]['locator']
    upload=client.post('/api/ai/attachments',headers=student,data={'course_id':1},files={'file':('图.png',image.getvalue())}).json()
    rejected=client.post('/api/ai/chat',headers=student,json={'course_id':1,'message':'看图','model':'deepseek-v4-pro','attachment_ids':[upload['id']]})
    assert rejected.status_code==422
    assert client.post('/api/ai/attachments',headers=student,data={'course_id':1},files={'file':('假.pdf',b'not a pdf')}).status_code==422
    assert client.post('/api/ai/attachments',headers=student,data={'course_id':1},files={'file':('run.exe',b'bad')}).status_code==422


def test_teacher_evidence_draft_save_and_targeted_assignment(client):
    teacher=headers(client,'teacher')
    student=headers(client)
    response=events(client.post('/api/ai/chat',headers=teacher,json={'course_id':1,'message':'这个班队列和栈有哪些典型错误？安排40分钟讲评课和两组后续练习。'}))
    done=response[-1]
    assert done['teaching']['method']=='DIA-TEACH'
    assert done['teaching']['evidence']['summary']['student_count']==28
    assert done['artifact'].get('id'),done
    artifact=done['artifact']
    draft_id=artifact['id']
    assert client.get(f'/api/ai/teacher-drafts/{draft_id}',headers=student).status_code==404
    first=client.post(f'/api/ai/teacher-drafts/{draft_id}/save',headers=teacher,json=artifact['draft'])
    assert first.status_code==200,first.text
    second=client.post(f'/api/ai/teacher-drafts/{draft_id}/save',headers=teacher,json=artifact['draft'])
    assert second.json()['resource_id']==first.json()['resource_id']
    group=artifact['draft']['groups'][0]
    assignment=client.post('/api/assignments',headers=teacher,json={'course_id':1,'title':'分组后续练习','class_id':1,'description':group['objective'],'question_ids':group['question_ids'],'student_ids':group['student_ids']})
    assert assignment.status_code==201,assignment.text


def test_general_question_has_no_arbitrary_knowledge_and_queue_mapping(client):
    student=headers(client)
    response=events(client.post('/api/ai/chat',headers=student,json={'course_id':1,'message':'这门课总共需要学习多久？'}))
    assert not response[-1]['teaching'].get('knowledge_id')
    response=events(client.post('/api/ai/chat',headers=student,json={'course_id':1,'message':'我不明白队列操作为什么错了'}))
    actions=response[-1]['teaching']['actions']
    assert any('mode=queue' in action.get('href','') for action in actions)
    assert not any('mode=stack' in action.get('href','') for action in actions)


def test_same_document_multiple_passages_and_teacher_private_filter(client):
    from backend.app.retrieval import retrieve
    with get_db() as db:
        db.execute("INSERT INTO resources(course_id,title,kind,content) VALUES(1,'队列多段材料','document',?)",('队列使用先进先出。\n\n队列在层序遍历中工作。',))
        db.execute("INSERT INTO resources(course_id,title,kind,content,metadata) VALUES(1,'教师私有答案','document','队列测验答案XYZ','{\"visibility\":\"teacher\"}')")
        citations=retrieve(db,1,'队列',user={'id':2,'role':'student'})
        matches=[item for item in citations if item['title']=='队列多段材料']
        assert len(matches)==2
        assert len({item['passage_id'] for item in matches})==2
        assert not any('XYZ' in item['excerpt'] for item in citations)


def test_development_budget_counts_reservations_across_requests(monkeypatch):
    from backend.app.ai_budget import reserve,finish
    from backend.app.ai import AIError
    monkeypatch.setenv('AI_DEV_BUDGET_SCOPE','pytest-'+uuid.uuid4().hex)
    monkeypatch.setenv('AI_DEV_REQUEST_LIMIT','2')
    first=reserve('deepseek-flash'); finish(first,'ok',{'prompt_tokens':4,'completion_tokens':3})
    second=reserve('deepseek-v4-pro'); finish(second,'network',{})
    with pytest.raises(AIError,match='预算'):
        reserve('deepseek-flash')


def test_teacher_light_path_and_question_draft_are_distinct(client):
    teacher=headers(client,'teacher')
    simple=events(client.post('/api/ai/chat',headers=teacher,json={'course_id':1,'message':'比较栈和队列的课堂提问建议'}))[-1]
    assert simple['teaching']['task']=='discussion'
    assert simple['teaching']['evidence']=={}
    generated=events(client.post('/api/ai/chat',headers=teacher,json={'course_id':2,'message':'围绕Python列表设计题目，生成一道单选题'}))[-1]
    assert generated['artifact']['kind']=='question'
    assert generated['artifact']['draft']['knowledge_id']
    assert 'options' in generated['artifact']['draft']
