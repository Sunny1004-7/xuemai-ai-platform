"""从唯一 TikZ 母版生成 README、技术文档和视频使用的矢量与位图。"""
import json
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
\begin{document}
\input{../../docs/technical-report/figures/overall-framework.tex}
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
    author = facts['author']
    (ROOT / 'docs/technical-report/submission-author.tex').write_text('\n'.join([
        r'\newcommand{\authorSchool}{' + author['school'] + '}',
        r'\newcommand{\authorMajor}{' + author['major'] + '}',
        r'\newcommand{\authorName}{' + author['name'] + '}',
    ]) + '\n', encoding='utf8')
    print('统一总框架图已导出，矢量文本与连接关系来自同一母版')


if __name__ == '__main__':
    build()
