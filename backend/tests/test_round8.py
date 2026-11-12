"""第八轮的术语检索与新增内容业务回归，全部使用独立数据和 Mock。"""
import json

import pytest
from fastapi.testclient import TestClient

from backend.app.db import get_db
from backend.app.main import app
from backend.app.retrieval import retrieve


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'round8.db'))
    monkeypatch.setenv('AI_MODE', 'mock')
    monkeypatch.setenv('AI_REQUESTS_PER_MINUTE', '30')
    with TestClient(app) as api:
        yield api


def login(client, username):
    response = client.post('/api/auth/login', json={'username': username, 'password': 'Xuemai123!'})
    assert response.status_code == 200
    return {'Authorization': 'Bearer ' + response.json()['token']}


@pytest.mark.parametrize('query, expected', [
    ('先放入的元素先取出，用于按到达先后处理', 'queue'),
    ('FIFO', 'queue'),
    ('先进先出', 'queue'),
    ('最后放入的元素先取出', 'stack'),
    ('LIFO', 'stack'),
    ('后进先出', 'stack'),
])
def test_ordering_paraphrases_rank_the_correct_source(client, query, expected):
    from backend.app.retrieval import ordering_concepts
    with get_db() as db:
        point = db.execute("SELECT id,course_id FROM knowledge_points WHERE title='栈与队列'").fetchone()
        citations = retrieve(db, point['course_id'], query, point['id'])
    assert citations
    assert expected in ordering_concepts(citations[0]['excerpt'])
    assert ordering_concepts(query) == {expected}


def test_ordering_comparison_and_negation():
    from backend.app.retrieval import ordering_concepts
    assert ordering_concepts('FIFO 和 LIFO 有什么区别') == {'queue', 'stack'}
    assert ordering_concepts('不是先进先出，而是后进先出') == {'stack'}
    assert ordering_concepts('先放入的元素最后取出') == {'stack'}
    assert ordering_concepts('队列名是一个 Python 字符串变量') == set()


def test_new_unit_uses_normal_authoring_retrieval_and_teaching_flow(client):
    teacher, student = login(client, 'teacher'), login(client, 'student1')

    def post(url, data, actor=teacher):
        response = client.post('/api' + url, json=data, headers=actor)
        assert response.status_code in (200, 201), response.text
        return response.json()

    course = post('/courses', {'title': '信息素养微单元', 'description': '原创例证：判断网络信息的可信度'})
    course_id = course['id']
    group = post('/classes', {'course_id': course_id, 'name': '信息核验体验班'})
    post('/classes/join', {'join_code': group['join_code']}, student)
    chapter = post(f'/courses/{course_id}/chapters', {'title': '来源交叉核验'})
    point = post(f'/courses/{course_id}/knowledge', {
        'title': '交叉核验', 'chapter_id': chapter['id'],
        'description': '追溯原始来源，再用相互独立的证据核验时间、对象和结论。',
    })
    resource = post('/resources', {
        'course_id': course_id, 'knowledge_id': point['id'], 'kind': 'document',
        'title': '校园节水消息核验讲义',
        'content': '# 三步核验\n\n校园节水消息标记为蓝鹭。先查原始发布方和日期，再找独立来源交叉核验，最后记录证据与尚待确认的问题。多个网站转载同一篇文章仍属于同一来源。',
    })
    question = post('/questions', {
        'course_id': course_id, 'knowledge_id': point['id'], 'type': 'single',
        'title': '三个网站转载同一则消息，可以视为三个独立来源吗？',
        'options': ['可以', '应追溯共同的原始来源'], 'answer': '应追溯共同的原始来源',
        'explanation': '独立性来自不同证据链，转载数量不能代替来源核验。',
    })
    post('/attempts', {'question_id': question['id'], 'answer': '可以'}, student)
    response = client.post('/api/ai/chat', headers=student, json={
        'course_id': course_id, 'knowledge_id': point['id'],
        'message': '根据蓝鹭讲义，我把转载当成独立来源，请给我核验提示。',
    })
    assert response.status_code == 200, response.text
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
    conversation_id = events[0]['conversation_id']
    history = client.get(f'/api/ai/conversations/{conversation_id}', headers=student).json()
    assistant = history['messages'][-1]
    assert assistant['status'] == 'complete'
    assert any(item.get('resource_id') == resource['id'] for item in assistant['citations'])
    task = post('/assignments', {
        'course_id': course_id, 'class_id': group['id'], 'knowledge_id': point['id'],
        'title': '核验来源练习', 'question_ids': [question['id']],
    })
    answer = post('/attempts', {
        'question_id': question['id'], 'assignment_id': task['id'],
        'answer': '应追溯共同的原始来源',
    }, student)
    assert answer['score'] == 100
    results = client.get(f"/api/assignments/{task['id']}/results", headers=teacher).json()
    assert len(results) == 1 and results[0]['completed'] and results[0]['score'] == 100
    followup = post('/classroom', {
        'course_id': course_id, 'class_id': group['id'], 'knowledge_id': point['id'],
        'title': '核验结论反馈', 'prompt': '说明为什么转载数量不等于独立来源数量。',
    })
    post(f"/classroom/{followup['id']}/responses", {'answer': '多个转载可能共享一条原始证据链，应独立查证。'}, student)
    activities = client.get('/api/classroom', params={'course_id': course_id}, headers=teacher).json()
    assert activities[0]['response_count'] == 1
