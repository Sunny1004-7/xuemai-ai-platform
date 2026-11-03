"""将源码对应的技术说明导出为中文 PDF，保留可核对的页数。"""
import html
from pathlib import Path
import re
import shutil

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def build():
    pdfmetrics.registerFont(TTFont('XueMaiCJK', 'C:/Windows/Fonts/msyh.ttc', subfontIndex=0))
    pdfmetrics.registerFont(TTFont('XueMaiCJK-Bold', 'C:/Windows/Fonts/msyhbd.ttc', subfontIndex=0))
    pdfmetrics.registerFontFamily('XueMaiCJK',normal='XueMaiCJK',bold='XueMaiCJK-Bold')
    destination = ROOT / '最终参赛提交材料' / '学脉XueMai-技术文档.pdf'
    destination.parent.mkdir(exist_ok=True)
    styles = {
        'body': ParagraphStyle('body',fontName='XueMaiCJK',fontSize=10.3,leading=16.5,textColor=colors.HexColor('#22334c'),spaceAfter=6,wordWrap='CJK'),
        'h1': ParagraphStyle('h1',fontName='XueMaiCJK',fontSize=24,leading=33,spaceBefore=14,spaceAfter=18,textColor=colors.HexColor('#21365e'),keepWithNext=True),
        'h2': ParagraphStyle('h2',fontName='XueMaiCJK',fontSize=15,leading=23,spaceBefore=14,spaceAfter=10,textColor=colors.HexColor('#244f72'),keepWithNext=True),
        'h3': ParagraphStyle('h3',fontName='XueMaiCJK',fontSize=12,leading=19,spaceBefore=9,spaceAfter=7,textColor=colors.HexColor('#277d70'),keepWithNext=True),
        'code': ParagraphStyle('code',fontName='XueMaiCJK',fontSize=9,leading=14,backColor=colors.HexColor('#f0f3f8'),borderPadding=7,spaceAfter=5,wordWrap='CJK'),
        'cell': ParagraphStyle('cell',fontName='XueMaiCJK',fontSize=9,leading=14,textColor=colors.HexColor('#22334c'),wordWrap='CJK'),
    }
    story=[]
    in_code=False
    def inline(text):
        text=html.escape(text)
        text=re.sub(r'\*\*(.*?)\*\*',r'<b>\1</b>',text)
        text=re.sub(r'`(.*?)`',r'<font color="#227b70">\1</font>',text)
        return re.sub(r'\[(.*?)\]\((.*?)\)',r'\1（\2）',text)
    lines=(ROOT/'docs/TECHNICAL_REPORT.md').read_text(encoding='utf-8').splitlines()
    pos=0
    while pos<len(lines):
        line=lines[pos]
        pos+=1
        if line.startswith('```'):
            in_code=not in_code
            continue
        if not line.strip():
            if pos>=2 and lines[pos-2].startswith('#'):
                continue
            story.append(Spacer(1,2*mm));continue
        if line.startswith('|') and not in_code:
            block=[line]
            while pos<len(lines) and lines[pos].startswith('|'):
                block.append(lines[pos]);pos+=1
            rows=[]
            for row in block:
                if re.match(r'^\|\s*[-:]+\s*\|',row):continue
                rows.append([Paragraph(inline(c.strip()),styles['cell']) for c in row.strip('|').split('|')])
            cols=len(rows[0]);width=172*mm
            widths=[width*.18,width*.39,width*.43] if cols==3 else [width/cols]*cols
            table=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7f0f5')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f7f9fc')]),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#aec1d1')),('BOTTOMPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7)]))
            story.append(table);story.append(Spacer(1,3*mm));continue
        style='code' if in_code else 'h1' if line.startswith('# ') else 'h2' if line.startswith('## ') else 'h3' if line.startswith('### ') else 'body'
        text=re.sub(r'^#{1,3}\s+','',line)
        text=inline(text)
        if text.startswith('- '):text='• '+text[2:]
        story.append(Paragraph(text,styles[style]))
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont('XueMaiCJK',8);canvas.setFillColor(colors.HexColor('#65748a'))
        canvas.drawString(19*mm,13*mm,'学脉 XueMai · 技术文档 · 2026-11-03')
        canvas.drawRightString(191*mm,13*mm,str(doc.page));canvas.restoreState()
    doc=SimpleDocTemplate(str(destination),pagesize=(210*mm,297*mm),rightMargin=19*mm,leftMargin=19*mm,topMargin=18*mm,bottomMargin=22*mm,title='学脉 XueMai 技术文档',author='XueMai 项目')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    count=len(PdfReader(destination).pages)
    if count>30:raise RuntimeError(f'技术文档超过30页：{count}')
    published=ROOT/'docs/deliverables/xuemai-technical-report.pdf'
    published.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(destination,published)
    print(f'技术文档已生成：{count} 页，{destination}')


if __name__=='__main__':build()

