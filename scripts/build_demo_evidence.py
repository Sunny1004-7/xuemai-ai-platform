"""从已保存原话生成适合1080p阅读的开发过程节选页。"""
from pathlib import Path
import html,re
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'docs/development-process/004-核心功能实际协作逐字转存.md').read_text(encoding='utf8')
parts=re.split(r'## 链[一二三]：',raw)[1:]
names=['课程与知识图谱','练习与学习证据','课程上下文辅导']
commits=['e040be6 · 版本化数据库与种子 / 9b40105 · 课程授权与先修关系','12fe7c2 · 评分与学习证据 / 143d3e1 · 目标计划驱动推荐','6ca03ae · 人工智能服务 / 449749e · 课程检索与教学草稿']
panels=[]
for i,part in enumerate(parts):
    quotes=re.findall(r'^> (.+)$',part,re.M)
    selected=[quotes[0],quotes[1],quotes[-1] if i==2 else quotes[3]]
    blocks=[]
    for label,text,limit in zip(['实际协作指令（节选）','实现反馈（节选）','修正与验证反馈（节选）'],selected,[420,210,210]):
        excerpt=text[:limit]+('……' if len(text)>limit else '')
        blocks.append(f'<article><h3>{label}</h3><p>{html.escape(excerpt)}</p></article>')
    panels.append(f'<section id="chain{i+1}"><header><small>已发生记录回放 · 初版核心协作 · 2026年11月3日</small><h1>0{i+1}　{names[i]}</h1></header><div class="quotes">{"".join(blocks)}</div><footer>对应提交　{commits[i]}<br>引文为可见原始消息节选，省略处用省略号标明。</footer></section>')
code='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><style>*{box-sizing:border-box}body{margin:0;background:#f1f0e8;color:#263a37;font-family:"Microsoft YaHei",sans-serif}section{display:none;height:1080px;padding:65px 105px 90px}section:target{display:block}small{font-size:21px;color:#52665f}h1{font:54px SimSun;margin:27px 0 38px}h3{font-size:22px;margin:0 0 18px;color:#2e6a67}p{font-size:22px;line-height:1.65;margin:0;overflow-wrap:anywhere}article{background:#fdfcf8;border-top:2px solid #a9c8be;padding:26px}article:first-child{grid-row:span 2}.quotes{display:grid;grid-template-columns:1.15fr 1fr;gap:24px}footer{font-size:20px;line-height:1.8;margin-top:25px;color:#52665f}pre{font:25px/1.8 "Consolas",monospace;background:#fdfcf8;padding:30px;white-space:pre-wrap}.flow{display:flex;gap:25px;margin:35px 0}.flow b{padding:30px;background:#d7e6db;font-size:26px}</style>'''+''.join(panels)+'''<section id="round2"><small>第二代学习引擎 · 当前代码与已发生提交</small><h1>每次更新，都保留计算依据</h1><div class="flow"><b>作答与提示</b><b>时间折减</b><b>证据更新</b><b>复习与教学动作</b></div><pre>衰减系数 = 2 ** (-间隔天数 / 30)
alpha = 1 + (alpha - 1) * 衰减系数
beta  = 3 + (beta - 3) * 衰减系数
知识估计 = alpha / (alpha + beta)</pre><footer>公式对应已提交的证据引擎，以上为中文等价表达。<br>c508eae　新增时间折减证据模型与间隔复习调度算法<br>56f6296　扩充六主题三十知识点课程并建立资源增量检索索引<br>de5b6b5　贯通学习证据理解检查与教师干预前后追踪</footer></section></html>'''
(ROOT/'docs/development-process/round2-replay.html').write_text(code,encoding='utf8')
print('已从原话生成四个独立回放画面')
