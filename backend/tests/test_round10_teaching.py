"""真实联调发现的草稿包裹格式兼容问题，保留业务校验。"""
import json
import pytest
from backend.app.teacher_assistant import extract_teacher_payload
from backend.tests.test_round6_ai import client, headers, events


@pytest.mark.parametrize('envelope',['<!--XM_TEACH:{payload}-->','<!--XM_TEACH\n{payload}\n-->','```json\n{payload}\n```'])
def test_alternative_envelopes_persist_same_validated_draft(client,monkeypatch,envelope):
    from backend.app.ai import AIService
    from backend.app.teacher_assistant import draft_sample
    async def stream(service,messages,**kwargs):
        # The normal Mock sample already contains the correct course-scoped draft.
        text=kwargs['mock_content'];raw=text.split('<!--XM_TEACH:',1)[1].split('-->',1)[0]
        service.last_usage={'prompt_tokens':0,'completion_tokens':0,'estimated':False}
        changed='简短的教学建议。'+envelope.format(payload=raw)
        for start in range(0,len(changed),7):yield changed[start:start+7]
    monkeypatch.setattr(AIService,'stream',stream)
    response=events(client.post('/api/ai/chat',headers=headers(client,'teacher'),json={'course_id':1,'knowledge_id':2,'message':'设计30分钟教案'}))
    done=response[-1]
    assert done['artifact'].get('id')
    assert 'XM_TEACH' not in done['content'] and '"steps"' not in done['content']
    assert not any('XM_TEACH' in e.get('content','') or '"steps"' in e.get('content','') for e in response if 'status' not in e)


def test_multiple_unmarked_json_blocks_remain_invalid():
    text='```json\n{}\n```\n```json\n{}\n```'
    assert extract_teacher_payload(text)[1] is None


def test_unclosed_marker_keeps_visible_prose_only():
    assert extract_teacher_payload('解释<!--XM_TEACH\n{"title":')==('解释',None)
