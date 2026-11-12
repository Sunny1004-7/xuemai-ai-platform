from backend.tests.test_round6_ai import client, events, headers


def test_teacher_design_keeps_requested_artifact_with_class_evidence(client):
    teacher = headers(client, 'teacher')
    result = events(client.post('/api/ai/chat', headers=teacher, json={
        'course_id': 1, 'class_id': 1, 'knowledge_id': 2,
        'message': '请基于这个班栈与队列的错误，设计一节30分钟讲评课。',
    }))[-1]
    assert result['teaching']['task'] == 'design'
    assert result['artifact']['id']
    assert sum(step['minutes'] for step in result['artifact']['draft']['steps']) <= 30


def test_teacher_discussion_remains_a_light_request(client):
    result = events(client.post('/api/ai/chat', headers=headers(client, 'teacher'), json={
        'course_id': 1, 'message': '比较栈和队列的课堂提问建议。',
    }))[-1]
    assert result['teaching']['task'] == 'discussion'
    assert result['teaching']['evidence'] == {}
