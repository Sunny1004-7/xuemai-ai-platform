"""核对当前实验、正式副本、完整截图与PDF结构，全部在本地执行。"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import pymupdf
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    facts=json.loads((ROOT/'docs/submission-facts.json').read_text('utf8'))
    manifest=json.loads((ROOT/'docs/experiments/round10/manifest.json').read_text('utf8'))
    for relative,expected in manifest['files'].items():
        assert digest(ROOT/relative)==expected,relative
    for relative,expected in facts['artifacts'].items():
        assert digest(ROOT/relative)==expected,relative
    pairs=[('docs/deliverables/xuemai-technical-report.pdf','最终参赛提交材料/学脉XueMai-技术文档.pdf'),
           ('docs/deliverables/xuemai-demo-1080p.mp4','最终参赛提交材料/学脉XueMai-演示视频-含旁白.mp4')]
    for a,b in pairs:assert digest(ROOT/a)==digest(ROOT/b)
    pdf=pymupdf.open(ROOT/pairs[0][0]);assert len(pdf)<=30
    assert '摘要' in pdf[2].get_text() and '1.1' not in pdf[2].get_text()
    assert '应用场景与总体方案' in pdf[3].get_text()
    assert '系统版本' not in pdf[0].get_text()
    main=(ROOT/'docs/technical-report/main.tex').read_text('utf8')
    abstract=(ROOT/'docs/technical-report/abstract-current.tex').read_text('utf8')
    assert len([p for p in abstract.split('\n\n') if p.strip()])==3
    assert '\\subsubsection' not in main
    links=sum(len(p.get_links()) for p in pdf)
    mapping=json.loads((ROOT/'docs/technical-report/完整截图来源.json').read_text('utf8'))
    directory=ROOT/facts['delivery']['screenshot_directory']
    images=[]
    for name,relative in mapping.items():
        with Image.open(directory/relative) as original,Image.open(ROOT/f'docs/technical-report/images/{name}.png') as output:
            assert original.size==output.size
            assert original.convert('RGB').tobytes()==output.convert('RGB').tobytes()
            images.append({'name':name,'size':list(output.size),'full_pixels_preserved':True})
    fonts=subprocess.check_output(['pdffonts',str(ROOT/pairs[0][0])],text=True,encoding='utf8')
    embedded=[re.search(r'\s+(yes|no)\s+(yes|no)\s+(yes|no)\s+\d+\s+\d+\s*$',line) for line in fonts.splitlines()[2:]]
    assert embedded and all(m and m[1]=='yes' for m in embedded)
    ledger=json.loads((ROOT/'docs/experiments/round10/token-ledger.json').read_text('utf8'))
    assert len(ledger['rows'])==202 and all(r['status']!='reserved' for r in ledger['rows'])
    assert sum(r['charged'] for r in ledger['rows'])==ledger['charged_or_reserved']<=ledger['limit']
    result={'experiment_files_verified':len(manifest['files']),'artifacts_verified':len(facts['artifacts']),
            'formal_copies_identical':True,'pdf_pages':len(pdf),'pdf_links':links,'fonts_embedded':len(embedded),
            'abstract_paragraphs':3,'abstract_independent_page':True,'two_heading_levels':True,
            'ui_image_sources':images,'token_rows':len(ledger['rows']),'tokens':ledger['charged_or_reserved'],
            'all_tokens_settled':True,'human_listening_review':False}
    (ROOT/'docs/rounds/第十轮交付一致性核验.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8',newline='\n')
    print(json.dumps({k:v for k,v in result.items() if k!='ui_image_sources'},ensure_ascii=False))


if __name__=='__main__':main()
