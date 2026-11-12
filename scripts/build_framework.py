"""从唯一 TikZ 母版生成 README、技术文档和视频使用的矢量与位图。"""
import json
import hashlib
from pathlib import Path
import subprocess

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/figures'


def build():
    OUT.mkdir(exist_ok=True)
    facts = json.loads((ROOT / 'docs/submission-facts.json').read_text('utf8'))
    local = ROOT / '.local/framework-build'
    local.mkdir(parents=True, exist_ok=True)
    source = r'''\documentclass[border=7pt]{standalone}
\usepackage{fontspec,xeCJK,tikz}
\setCJKmainfont{SimSun}[AutoFakeBold=2.2]
\setmainfont{Times New Roman}
\usetikzlibrary{arrows.meta,positioning,calc}
\definecolor{celadon}{HTML}{2E6A67}
\definecolor{pale}{HTML}{D7E6DB}
\definecolor{tea}{HTML}{7E6554}
\definecolor{rice}{HTML}{E9D6BE}
\newwrite\frameworkregionsfile
\immediate\openout\frameworkregionsfile=regions.csv
\begin{document}
\input{../../docs/technical-report/figures/overall-framework.tex}%
\immediate\closeout\frameworkregionsfile
\end{document}'''
    (local / 'framework.tex').write_text(source, encoding='utf8')
    result = subprocess.run(['xelatex', '-interaction=nonstopmode', '-halt-on-error', 'framework.tex'], cwd=local, capture_output=True)
    (local / 'compile.log').write_bytes(result.stdout)
    result.check_returncode()
    pdf = (local / 'framework.pdf').read_bytes()
    (OUT / 'xuemai-framework.pdf').write_bytes(pdf)
    document = pymupdf.open(stream=pdf, filetype='pdf')
    page = document[0]
    page.get_pixmap(matrix=pymupdf.Matrix(2400 / page.rect.width, 2400 / page.rect.width)).save(OUT / 'xuemai-framework.png')
    # 字形路径化 SVG 在浏览器及离线阅读中保持一致。可编辑文本和连线保留于 TikZ 母版。
    subprocess.run(['pdftocairo', '-svg', str(OUT / 'xuemai-framework.pdf'), str(OUT / 'xuemai-framework.svg')], check=True)
    anchors = {}
    for line in (local / 'regions.csv').read_text('utf8').splitlines():
        name, *values = line.split(',')
        anchors[name] = [float(value.removesuffix('pt')) for value in values]
    left, bottom, right, top = anchors.pop('canvas')
    pt_to_bp = 72 / 72.27
    border = 7 * pt_to_bp
    expected = ((right - left) * pt_to_bp + 2 * border, (top - bottom) * pt_to_bp + 2 * border)
    if max(abs(expected[0] - page.rect.width), abs(expected[1] - page.rect.height)) > .1:
        raise RuntimeError('图形页面与TikZ边界不一致')
    nodes = {name: {'x': (x1-left)*pt_to_bp+border, 'y': (top-y2)*pt_to_bp+border,
                    'width': (x2-x1)*pt_to_bp, 'height': (y2-y1)*pt_to_bp}
             for name, (x1,y1,x2,y2) in anchors.items()}
    members = {'inputs':['si','ti'], 'shared-evidence':['data'], 'student-methods':['k','p','g'],
               'teacher-methods':['c','t'], 'services':['service'], 'workspaces':['so','to'], 'feedback':['feedback']}
    groups = {}
    for name, identifiers in members.items():
        boxes = [nodes[identifier] for identifier in identifiers]
        x, y = min(box['x'] for box in boxes), min(box['y'] for box in boxes)
        groups[name] = {'members': identifiers, 'x':x, 'y':y,
                        'width':max(box['x']+box['width'] for box in boxes)-x,
                        'height':max(box['y']+box['height'] for box in boxes)-y}
    regions = {'coordinate_system':'PDF points, top-left origin', 'width':page.rect.width,
               'height':page.rect.height, 'nodes':nodes, 'groups':groups,
               'source':'docs/technical-report/figures/overall-framework.tex',
               'source_sha256':hashlib.sha256((ROOT/'docs/technical-report/figures/overall-framework.tex').read_text('utf8').encode('utf8')).hexdigest(),
               'source_digest_encoding':'UTF-8 with LF line endings'}
    (OUT / 'xuemai-framework-regions.json').write_text(json.dumps(regions,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    author = facts['author']
    current = json.loads((ROOT / 'docs/demo/current.json').read_text('utf8'))
    video_project = ROOT / current['project']
    video_project.mkdir(parents=True, exist_ok=True)
    video_facts = {key:facts[key] for key in ['product','subtitle','version','track','author','focus','methods','method_definitions']}
    (video_project / 'product.json').write_text(json.dumps(video_facts, ensure_ascii=False, indent=2), encoding='utf8')
    (ROOT / 'docs/technical-report/submission-author.tex').write_text('\n'.join([
        r'\newcommand{\authorSchool}{' + author['school'] + '}',
        r'\newcommand{\authorMajor}{' + author['major'] + '}',
        r'\newcommand{\authorName}{' + author['name'] + '}',
        r'\newcommand{\applicationFocus}{' + facts['focus'] + '}',
    ]) + '\n', encoding='utf8')
    definitions = facts['method_definitions']
    (ROOT / 'docs/technical-report/method-names.tex').write_text('\n'.join(
        r'\newcommand{\method' + row['tex_key'] + '}{' + row['name'] + '（' + row['english'] + '，' + row['chinese'] + '）}'
        for row in definitions) + '\n', encoding='utf8')
    (ROOT / 'docs/METHOD_TERMS.md').write_text('# 核心教学方法名称\n\n以下为学脉结合实际机制定义的方法名称。\n\n' + '\n\n'.join(
        row['name'] + '（' + row['english'] + '，' + row['chinese'] + '）。' for row in definitions) + '\n', encoding='utf8')
    print('统一总框架图已导出，矢量文本与连接关系来自同一母版')


if __name__ == '__main__':
    build()
