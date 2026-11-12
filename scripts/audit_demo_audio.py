"""以本地语音识别回验正式旁白，并保留原始转写与时间轴检查。"""
import hashlib
import json
from pathlib import Path
import re
import os
from difflib import SequenceMatcher

from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parents[1]


def normalize(text):
    return re.sub(r'[^\u4e00-\u9fffA-Za-z0-9]', '', text).lower()


def main():
    source = ROOT / '最终参赛提交材料/学脉XueMai-演示视频-含旁白.mp4'
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    latest = os.environ.get('XUEMAI_VIDEO_ROUND') == '8'
    target = ROOT / ('docs/demo/第八轮语音转写回验.json' if latest else 'docs/demo/第七轮语音转写回验.json')
    model = WhisperModel(str(ROOT / '.local/models/faster-whisper-small'), device='cpu', compute_type='int8', cpu_threads=6)
    segments, info = model.transcribe(str(source), language='zh', beam_size=3, vad_filter=True,
                                     word_timestamps=True, condition_on_previous_text=False,
                                     initial_prompt='学脉，陈星河，栈与队列，Codex，DeepSeek Flash，课程，知识证据，迁移应用。')
    decoded = []
    words = []
    for segment in segments:
        decoded.append({'start': segment.start, 'end': segment.end, 'text': segment.text})
        words.extend({'start': word.start, 'end': word.end, 'text': word.word} for word in segment.words)
        print(round(segment.start, 1), segment.text, flush=True)
    scenes = json.loads((ROOT / ('docs/demo/第八轮演示源/scenes.json' if latest else 'scripts/demo-scenes.json')).read_text('utf8'))
    per_scene = []
    for scene in scenes:
        actual = ''.join(word['text'] for word in words if scene['start']-.12 <= word['start'] < scene['start']+scene['duration']-.1)
        per_scene.append({'scene': scene['name'], 'start': scene['start'], 'expected': scene['text'], 'transcribed': actual,
                          'character_similarity': round(SequenceMatcher(None, normalize(scene['text']), normalize(actual)).ratio(), 4)})
    voices = json.loads((ROOT / ('docs/demo/第八轮演示源/audio/segments.json' if latest else '.local/narration/segments.json')).read_text('utf8'))
    gaps = [right['start'] - left['start'] - left['duration'] for left, right in zip(voices, voices[1:])]
    expected = ''.join(scene['text'] for scene in scenes)
    actual = ''.join(segment['text'] for segment in decoded)
    result = {'method': '本地Whisper small中文自动回转写，保留原文与逐场景对应；关键操作字幕另作可视核对',
              'source_video_sha256': digest, 'language_probability': info.language_probability,
              'global_character_similarity': round(SequenceMatcher(None, normalize(expected), normalize(actual), autojunk=False).ratio(), 4),
              'max_narration_tempo': max(voice['tempo'] for voice in voices), 'max_gap_seconds': round(max(gaps), 3),
              'voice_segments': len(voices), 'no_voice_overlap': min(gaps) >= -.005,
              'raw_segments': decoded, 'scenes': per_scene}
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    if not result['no_voice_overlap'] or result['max_gap_seconds'] > 8 or result['global_character_similarity'] < .8:
        raise RuntimeError('自动回验需要复核，请查看原始转写及场景对应')
    print(json.dumps({key: value for key, value in result.items() if key not in {'raw_segments', 'scenes'}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
