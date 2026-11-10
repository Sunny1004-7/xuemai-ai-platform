"""核对实际主题中的关键文字组合，原始色板保持不变。"""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def luminance(color):
    c=[int(color[i:i+2],16)/255 for i in (1,3,5)]
    c=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in c]
    return sum(a*b for a,b in zip(c,[.2126,.7152,.0722]))
def contrast(a,b):
    x,y=sorted([luminance(a),luminance(b)]);return (y+.05)/(x+.05)
pairs=[('学生正文','#263A37','#F1F0E8'),('学生辅助文字','#52665F','#F1F0E8'),('学生主按钮','#FFFFFF','#2E6A67'),('教师正文','#352D29','#F5EEE4'),('教师辅助文字','#695A50','#F5EEE4'),('教师主按钮','#FFFFFF','#7E6554'),('学生柱图数值','#263A37','#A9C8BE'),('教师柱图数值','#352D29','#D4B79D')]
rows=[{'usage':n,'foreground':a,'background':b,'ratio':round(contrast(a,b),2),'passes_normal_text':contrast(a,b)>=4.5} for n,a,b in pairs]
if not all(r['passes_normal_text'] for r in rows):raise RuntimeError('关键文字对比不足')
(ROOT/'docs/design-contrast.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(rows,ensure_ascii=False))
