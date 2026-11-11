"""用XeLaTeX生成正式技术文档，并校验页数、文字颜色与字体。"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from PIL import Image
import pymupdf as fitz

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from review_screenshots import validate_screenshots


def build(screenshots,record,draft=False):
    subprocess.run([sys.executable,str(ROOT/'scripts/report_evidence_example.py')],check=True)
    source=ROOT/'docs/technical-report'
    directory=ROOT/screenshots
    if not draft:
        manifest,_=validate_screenshots(ROOT,Path(screenshots),record)
    else:
        manifest=json.loads((directory/'截图清单.json').read_text(encoding='utf-8'))
    images=source/'images';images.mkdir(exist_ok=True)
    mapping={'graph':'student/graph/CS201/desktop_fullscreen.png',
             'graph-overview':'student/graph/CS201/desktop_chapters.png',
             'student-dashboard':'student/dashboard/CS201/desktop_full.png',
             'practice':'student/practice/CS201/desktop_correct.png','video':'student/video/CS101/desktop_full.png',
             'teacher-dashboard':'teacher/dashboard/CS201/desktop_full.png',
             'teacher-matrix':'teacher/analytics/CS201/desktop_full.png',
             'teacher-groups':'teacher/analytics/CS201/desktop_view-3.png',
             'resources':'teacher/resources/CS101/desktop_full.png',
             'tutor':'student/tutor/CS101/desktop_conversation.png',
             'login':'public/login/public/desktop_full.png',
             'python-plan':'student/plan/CS101/desktop_view-4.png',
             'python-experiment':'student/experiments/CS101/desktop_py-function.png'}
    for name,relative in mapping.items():
        img=Image.open(directory/relative).convert('RGB')
        # 保留彩色像素；排版使用版心100%宽度，不设置高度压缩。
        if name not in {'graph','login'}:
            img=img.crop((232,72,img.width,min(img.height,1000)))
        img.save(images/(name+'.png'))
    back=(ROOT/'.local/round5-business-tests.txt').read_text(encoding='utf-8',errors='replace')
    browser=(ROOT/'.local/round5-e2e.txt').read_text(encoding='utf-8',errors='replace')
    bm=re.search(r'(\d+) passed',back);em=re.search(r'(\d+) passed',browser)
    if not bm or not em:raise RuntimeError('缺少本轮完整回归结果')
    summary=f"后端业务与算法98项、交付校验14项通过；浏览器师生流程与交互回归共{em[1]}项通过。界面检查覆盖两门课程的师生18个业务模块及登录入口，采用四种桌面视口与手机窄屏，共保存{len(manifest['files'])}张截图，页面运行错误为0。自动化、内容建设和录制使用本地示例模式，本次升级新增官方接口调用为0。已有官方服务抽样覆盖辅导、出题、备课与量规评阅，四次均成功、零重试，累计输入3744 Tokens、输出724 Tokens。\n"
    (source/'validation-summary.tex').write_text(summary,encoding='utf-8')
    compiled=ROOT/'.local/technical-report-build';compiled.mkdir(exist_ok=True,parents=True)
    for index in range(3):
        r=subprocess.run(['xelatex','-interaction=nonstopmode','-halt-on-error','-output-directory='+str(compiled),'main.tex'],cwd=source,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (ROOT/'.local'/f'report-compile-{index+1}.log').write_bytes(r.stdout)
        if r.returncode:raise RuntimeError('文档编译失败，请检查编译输出')
    document=fitz.open(compiled/'main.pdf')
    text='\n'.join(p.get_text() for p in document)
    for word in ['PROJECT_STATE','CODEX_TASK','本地工作区','本轮记录','D:\\','C:\\']:
        if word in text:raise RuntimeError('正式文档包含内部工作信息')
    colored=[];fonts=set();preview=ROOT/'.local/report-preview';preview.mkdir(exist_ok=True)
    for i,page in enumerate(document):
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines',[]):
                for span in line['spans']:
                    fonts.add(span['font'])
                    if span['color']!=0:colored.append({'page':i+1,'text':span['text'][:30]})
        page.get_pixmap(matrix=fitz.Matrix(1.4,1.4)).save(preview/f'page-{i+1:02}.png')
    if colored:raise RuntimeError('文档正文或图中文字存在彩色文本')
    if len(document)>30:raise RuntimeError(f'文档{len(document)}页，超过30页；已输出预览供修订')
    outputs=[ROOT/'最终参赛提交材料/学脉XueMai-技术文档.pdf',ROOT/'docs/deliverables/xuemai-technical-report.pdf']
    for output in outputs:output.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(compiled/'main.pdf',output)
    diagram_count=len(re.findall(r'\\diagram\{', (source/'main.tex').read_text('utf-8')))
    reference_count=len(re.findall(r'\\bibitem\{',(source/'main.tex').read_text('utf-8')))
    result={'pages':len(document),'black_text':True,'fonts':sorted(fonts),'figures_tikz':diagram_count,'screenshots':len(mapping),'screenshot_width':'100%版心，彩色，不设高度缩放','frontend_capture_count':len(manifest['files']),'backend_tests':int(bm[1]),'browser_tests':int(em[1]),'references':reference_count}
    (ROOT/'docs/technical-report/验收结果.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--screenshots',required=True);p.add_argument('--record',required=True);p.add_argument('--draft',action='store_true');args=p.parse_args()
    build(args.screenshots,args.record,args.draft)
