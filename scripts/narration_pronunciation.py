"""只改变语音输入中的缩写读法，字幕继续使用原始讲稿。"""


def prepare_speech(text: str) -> tuple[str, list[int]]:
    spoken = []
    positions = []
    index = 0
    while index < len(text):
        if text[index:index + 2] == 'AI':
            # 分开大写字母，让中文神经语音依次读英语字母A和I。
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
