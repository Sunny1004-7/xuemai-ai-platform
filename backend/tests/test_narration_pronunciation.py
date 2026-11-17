"""缩写发音调整不应改变讲稿或字幕坐标。"""
from scripts.narration_pronunciation import join_ai_audio, original_boundary, prepare_speech, remap_audio_time
from array import array
import math
import wave


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


def test_ai_vowels_join_without_silent_letter_gap_and_later_timing_follows(tmp_path):
    rate = 24000
    voiced = lambda freq: array('h', (round(6000 * math.sin(2 * math.pi * freq * i / rate)) for i in range(round(.2 * rate))))
    samples = voiced(220) + array('h', [0] * round(.08 * rate)) + voiced(260)
    source, output = tmp_path / 'letters.wav', tmp_path / 'word.wav'
    with wave.open(str(source), 'wb') as wav:
        wav.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        wav.writeframes(samples.tobytes())
    words = [{'text': 'A', 'offset': 0, 'duration': 2000000}, {'text': 'I', 'offset': 2800000, 'duration': 2000000}]
    cuts = join_ai_audio(source, output, words)
    assert len(cuts) == 1 and cuts[0]['gap_before_ms'] >= 75
    with wave.open(str(output)) as wav:
        actual = array('h', wav.readframes(wav.getnframes()))
        seconds = wav.getnframes() / rate
    assert .37 < seconds < .41
    assert abs(remap_audio_time(.48, cuts) - seconds) < 1 / rate
    # 连接处继续有声，无完整10ms静音块，避免把分读停顿留在成品。
    assert all(any(actual[j:j + 240]) for j in range(0, len(actual) - 240, 240))


def test_already_connected_audio_is_preserved(tmp_path):
    rate = 24000
    samples = array('h', (round(6000 * math.sin(2 * math.pi * 220 * i / rate)) for i in range(9600)))
    source, output = tmp_path / 'connected.wav', tmp_path / 'output.wav'
    with wave.open(str(source), 'wb') as wav:
        wav.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        wav.writeframes(samples.tobytes())
    words = [{'text': 'A', 'offset': 0, 'duration': 2000000}, {'text': 'I', 'offset': 2000000, 'duration': 2000000}]
    assert join_ai_audio(source, output, words) == []
    assert output.read_bytes() == source.read_bytes()
