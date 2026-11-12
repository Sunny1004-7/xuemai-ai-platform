"""按标点语义与实际字体宽度组织单行字幕。"""
import re


def semantic_lines(text, measure, max_width=1440):
    """保留术语内部字符，仅在讲稿已有的自然停顿处分条。"""
    clauses = re.findall(r'[^，。！？；：]+[，。！？；：]?|[，。！？；：]', text)
    lines = []
    current = ''
    for clause in clauses:
        if measure(clause) > max_width:
            raise ValueError('语义片段超出字幕安全宽度，请在讲稿自然停顿处调整标点。')
        if current and measure(current + clause) > max_width:
            lines.append(current)
            current = ''
        current += clause
        if clause.endswith(('。', '！', '？', '；')):
            lines.append(current)
            current = ''
    if current:
        lines.append(current)
    if ''.join(lines) != text:
        raise ValueError('字幕与讲稿文字不一致')
    return lines
