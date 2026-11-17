"""缩写发音调整不应改变讲稿或字幕坐标。"""
from scripts.narration_pronunciation import original_boundary, prepare_speech


def test_separated_letters_map_back_to_ai_without_changing_caption():
    text = '下面介绍AI教学助手，以及AI协同过程。'
    spoken, positions = prepare_speech(text)
    assert spoken == '下面介绍A I教学助手，以及A I协同过程。'
    for start in [spoken.index('A I'), spoken.rindex('A I')]:
        begin, end = original_boundary(positions, start, start + 3)
        assert text[begin:end] == 'AI'
        begin, end = original_boundary(positions, start + 2, start + 3)
        assert text[begin:end] == 'I'
    begin, end = original_boundary(positions, spoken.index('教学助手'), spoken.index('教学助手') + 4)
    assert text[begin:end] == '教学助手'


def test_unaffected_text_keeps_existing_voice_cache_input_and_coordinates():
    text = '教师查看课程，再安排下一步学习。'
    spoken, positions = prepare_speech(text)
    assert spoken == text
    assert positions == list(range(len(text)))
