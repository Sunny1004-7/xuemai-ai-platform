"""为报告生成可重复的合成作答计算表，不改动业务数据库。"""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.app.evidence import estimate_state,update_state
t=datetime(2026,11,10,tzinfo=timezone.utc)
state=estimate_state(now=t);rows=[{'label':'初始先验','weight':0,**state}]
samples=[('甲：独立答对',True,1,0,None),('乙：提示后答对',True,2,1,None),('丙：首次答错',False,2,0,None),('丙：短期订正',True,2,0,{'created_at':t.isoformat(),'correct':False}),('丙：再次答对',True,2,0,{'created_at':t.isoformat(),'correct':True})]
for label,correct,difficulty,hints,previous in samples:
    state=update_state(state,correct,difficulty,hints,previous,t)
    rows.append({'label':label,**state})
folded=estimate_state({**state,'updated_at':t.isoformat()},t+timedelta(days=30))
rows.append({'label':'30天无新证据','weight':0,**folded})
out=ROOT/'docs/technical-report'
(out/'evidence-example.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
table='\\begin{table}[H]\\centering\\caption{同一知识点的合成证据更新示例}\\begin{tabularx}{\\linewidth}{Yrrrrr}\\toprule 场景&权重&$\\alpha$&$\\beta$&估计&有效证据\\\\\\midrule\n'
for r in rows:table+=r['label']+'&'+'&'.join(f'{r[k]:.3f}' for k in ['weight','alpha','beta','value','effective_count'])+'\\\\\n'
table+='\\bottomrule\\end{tabularx}\\end{table}\n'
(out/'evidence-example.tex').write_text(table,encoding='utf8')
print('已生成',len(rows),'行计算结果')
