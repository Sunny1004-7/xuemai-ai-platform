"""生成准确的字母音素并连接为连续AI读音，字幕继续使用原始讲稿。"""
from array import array
import math
from pathlib import Path
import wave


def prepare_speech(text: str) -> tuple[str, list[int]]:
    spoken = []
    positions = []
    index = 0
    while index < len(text):
        if text[index:index + 2] == 'AI':
            # 先取得准确的A/I音素；最终音频由join_ai_audio消除分读停顿。
            spoken.extend('A I')
            positions.extend([index, index, index + 1])
            index += 2
        else:
            spoken.append(text[index])
            positions.append(index)
            index += 1
    return ''.join(spoken), positions


def original_boundary(positions: list[int], begin: int, end: int) -> tuple[int, int]:
    if not 0 <= begin < end <= len(positions):
        raise ValueError('语音词语边界超出原稿映射范围')
    return positions[begin], positions[end - 1] + 1


def remap_audio_time(seconds: float, cuts: list[dict]) -> float:
    shift = 0.0
    for cut in cuts:
        begin, end, fade = cut['begin'], cut['end'], cut['fade']
        if seconds >= end:
            shift += end - begin - fade
        elif seconds > begin:
            return begin - shift + (seconds - begin) * fade / (end - begin)
        else:
            break
    return seconds - shift


def join_ai_audio(source: Path, destination: Path, words: list[dict]) -> list[dict]:
    """只处理A/I两音素之间的低能量空档，用15ms交叉淡化连续衔接。"""
    with wave.open(str(source)) as audio:
        params = audio.getparams()
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2:
            raise ValueError('AI连读处理需要单声道16位PCM')
        samples = array('h', audio.readframes(audio.getnframes()))
        rate = audio.getframerate()
    step = max(1, round(rate * .005))
    fade = round(rate * .015)
    cuts = []
    for first, second in zip(words, words[1:]):
        if first.get('text') != 'A' or second.get('text') != 'I':
            continue
        begin = max(0, round(first['offset'] / 1e7 * rate))
        middle = round(second['offset'] / 1e7 * rate)
        end = min(len(samples), round((second['offset'] + second['duration']) / 1e7 * rate))
        blocks = [(at, math.sqrt(sum(value * value for value in samples[at:at + step]) / step))
                  for at in range(begin, end - step, step)]
        left = max((i for i, block in enumerate(blocks) if block[0] < middle), key=lambda i: blocks[i][1])
        right = max((i for i, block in enumerate(blocks) if block[0] >= middle), key=lambda i: blocks[i][1])
        if right <= left + 1:
            continue
        valley = min(range(left + 1, right), key=lambda i: blocks[i][1])
        threshold = .22 * min(blocks[left][1], blocks[right][1])
        if blocks[valley][1] >= threshold:
            continue
        low = high = valley
        while low > left + 1 and blocks[low - 1][1] < threshold:
            low -= 1
        while high < right - 1 and blocks[high + 1][1] < threshold:
            high += 1
        a, b = blocks[low][0], blocks[high][0] + step
        if b - a < round(.01 * rate) or a < fade or b + fade > len(samples):
            continue
        cuts.append({'begin': (a - fade) / rate, 'end': (b + fade) / rate,
                     'fade': fade / rate, 'gap_before_ms': round((b - a) / rate * 1000, 2),
                     'removed_ms': round((b - a + fade) / rate * 1000, 2)})
    rendered = array('h')
    cursor = 0
    for cut in cuts:
        a, b, count = round(cut['begin'] * rate), round(cut['end'] * rate), round(cut['fade'] * rate)
        rendered.extend(samples[cursor:a])
        for i in range(count):
            weight = (i + 1) / (count + 1)
            value = samples[a + i] * (1 - weight) + samples[b - count + i] * weight
            rendered.append(round(value))
        cursor = b
    rendered.extend(samples[cursor:])
    with wave.open(str(destination), 'wb') as output:
        output.setparams(params)
        output.writeframes(rendered.tobytes())
    return cuts
