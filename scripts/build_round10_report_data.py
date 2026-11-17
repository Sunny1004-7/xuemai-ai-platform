"""只读取已完成实验，生成统一摘要与可编辑统计图，不发起网络请求。"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import random
import re
import sys
import subprocess

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
DATA=ROOT/'docs/experiments/round10'
REPORT=ROOT/'docs/technical-report'


def read(name):return json.loads((DATA/name).read_text('utf8'))


def evaluate():
    protocol=read('protocol.json')
    tasks=[t for t in protocol['tasks'] if t['split']=='eval']
    rows=[]
    for task in tasks:
        for condition in ['full','baseline']:
            result=read('real/'+task['id']+'-'+condition+'.json')
            successful=result['api_complete'];events=result.get('events',[])
            done=next((e for e in reversed(events) if e.get('status')=='complete'),{})
            content=done.get('content','');plan=done.get('teaching',{});artifact=done.get('artifact',{})
            needs_artifact=task['role']=='teacher' and task['kind'] in ['mixed','lesson','groups','question','rubric','feedback']
            structured=bool(artifact.get('id')) if needs_artifact else bool(plan.get('check')) if task['role']=='student' else successful
            source_mentions=re.findall(r'\[(\d+)\]',content)
            citations=next((e.get('citations',[]) for e in events if e.get('citations')),[])
            located=bool(citations) and all(c.get('locator') and c.get('version') for c in citations)
            valid_references=bool(source_mentions) and all(1<=int(n)<=len(citations) for n in source_mentions)
            saved=result.get('checks',{}).get('saved',True)
            completed=successful and structured and saved and result.get('checks',{}).get('persisted',False)
            rows.append({'task_id':task['id'],'condition':condition,'role':task['role'],'kind':task['kind'],
                         'model':task['model'],'api_complete':successful,'structure_valid':structured,
                         'source_located':located,'reference_number_valid':valid_references,'business_complete':completed,
                         'seconds':result['elapsed_seconds'],'artifact_status':artifact.get('status')})
    by_condition={}
    for condition in ['full','baseline']:
        chosen=[r for r in rows if r['condition']==condition]
        by_condition[condition]={'tasks':len(chosen),**{k:sum(r[k] for r in chosen) for k in
            ['api_complete','structure_valid','source_located','reference_number_valid','business_complete']},
            'mean_seconds':statistics.mean(r['seconds'] for r in chosen)}
    kinds={}
    for role,kind in sorted({(r['role'],r['kind']) for r in rows}):
        kinds[role+'/'+kind]={c:{'tasks':sum(r['condition']==c and r['role']==role and r['kind']==kind for r in rows),
                               'business_complete':sum(r['business_complete'] for r in rows if r['condition']==c and r['role']==role and r['kind']==kind)}
                           for c in ['full','baseline']}
    return {'independent_tasks':len(tasks),'responses':len(rows),'conditions':by_condition,'by_kind':kinds,'rows':rows}


def figures(summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'SimSun','font.size':11,'axes.spines.top':False,'axes.spines.right':False,
                         'pdf.fonttype':42,'svg.fonttype':'none','text.color':'black','axes.labelcolor':'black',
                         'xtick.color':'black','ytick.color':'black'})
    path=read('path.json');cases=[c for c in path['cases'] if c['split']=='eval']
    fig,axes=plt.subplots(1,2,figsize=(7.4,2.55),layout='constrained')
    for budget,color in zip([10,20,30,60],['#2e6a67','#607e95','#7e6554','#a09068']):
        chosen=[c for c in cases if c['budget']==budget]
        axes[0].scatter([c['outcomes']['feasible_greedy']['utility'] for c in chosen],
                        [c['outcomes']['PATH-G']['utility'] for c in chosen],s=9,alpha=.55,color=color,label=f'{budget}分钟')
    axes[0].plot([0,85],[0,85],color='#555555',lw=.7,ls='--')
    axes[0].set(xlabel='可行贪心效用',ylabel='PATH-G效用',xlim=(0,85),ylim=(0,85));axes[0].legend(fontsize=8,frameon=False)
    budgets=[10,20,30,60]
    for method,color in [('PATH-G','#2e6a67'),('feasible_greedy','#7e6554')]:
        axes[1].plot(budgets,[statistics.mean(c['outcomes'][method]['budget_utilization'] for c in cases if c['budget']==b)*100 for b in budgets],
                     marker='o',color=color,label='PATH-G' if method=='PATH-G' else '可行贪心')
    axes[1].set(xlabel='时间预算（分钟）',ylabel='预算利用率（%）',ylim=(50,100));axes[1].legend(fontsize=9,frameon=False)
    out=ROOT/'docs/figures/round10';out.mkdir(exist_ok=True,parents=True)
    for extension in ['pdf','svg','png']:fig.savefig(out/('path-comparison.'+extension),dpi=220)
    plt.close(fig)
    # K-TRACE distribution: same evaluation trajectories for every method.
    ktrace=read('ktrace.json');rows=[c for c in ktrace['cases'] if c['split']=='eval']
    names=['K-TRACE','no_decay','no_hints','no_correlation','fixed_step']
    fig,ax=plt.subplots(figsize=(7.2,2.4),layout='constrained')
    ax.boxplot([[r['rmse'][m] for r in rows] for m in names],tick_labels=['K-TRACE','无时间折减','无提示修正','无相关修正','固定增减'],
               showfliers=False,patch_artist=True,boxprops={'facecolor':'#d7e6db'},medianprops={'color':'black'})
    ax.set_ylabel('轨迹均方根误差')
    for extension in ['pdf','svg','png']:fig.savefig(out/('ktrace-distribution.'+extension),dpi=220)
    plt.close(fig)


def main():
    if '--materials-only' in sys.argv:
        manifest=read('manifest.json')
        for relative,expected in manifest['files'].items():
            if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=expected:
                raise ValueError('已完成实验文件发生变化：'+relative)
        subprocess.run([sys.executable,str(ROOT/'scripts/build_round10_sections.py')],cwd=ROOT,check=True)
        subprocess.run([sys.executable,str(ROOT/'scripts/build_round10_figures.py')],cwd=ROOT,check=True)
        print('已核对完成的实验，沿用统计图与逐例结果，更新文稿和方法图源')
        return
    local={name:read(name+'.json') for name in ['ktrace','path','class','retrieval']}
    real=evaluate();tokens=read('token-ledger.json');business=read('end-to-end.json')
    # Post-evidence change stress checks use the already frozen class inputs.
    from backend.app.learning_insights import dynamic_groups
    questions=[{'id':k*4+j+1,'knowledge_id':k+1,'skill':skill,'difficulty':2}
               for k in range(4) for j,skill in enumerate(['concept','procedure','reasoning','transfer'])]
    changes=[]
    from copy import deepcopy
    for case in local['class']['cases']:
        if case['split']!='eval' or case['family']!=5:continue
        students=deepcopy(case['students']);student=students[0]
        student['features']=students[1]['features'].copy()
        student['feature_confidence']=students[1]['feature_confidence'].copy()
        student['weak_knowledge_ids']=students[1]['weak_knowledge_ids'].copy()
        after=dynamic_groups(students,questions)
        before_focus=next(g['focus'] for g in case['groups'] if student['id'] in g['student_ids'])
        after_focus=next(g['focus'] for g in after if student['id'] in g['student_ids'])
        changes.append({'class_id':case['id'],'student_id':student['id'],'before_focus':before_focus,
                        'after_focus':after_focus,'focus_changed':before_focus!=after_focus,'after_groups':after})
    change_result={'source':'class.json frozen eval family 5','scenarios':len(changes),
                   'changed':sum(c['focus_changed'] for c in changes),'cases':changes}
    (DATA/'class-change.json').write_text(json.dumps(change_result,ensure_ascii=False,indent=2),encoding='utf8',newline='\n')
    if tokens['charged_or_reserved']>tokens['limit']:raise ValueError('Token预算超限')
    path=local['path'];greedy=path['summary']['feasible_greedy']['utility'];beam=path['summary']['PATH-G']['utility']
    # Cluster bootstrap keeps all budgets belonging to each independently generated graph together.
    groups={}
    for c in path['cases']:
        if c['split']=='eval':groups.setdefault(c['graph'],[]).append(c)
    rng=random.Random(101711);keys=list(groups);gains=[]
    for _ in range(1000):
        chosen=[c for k in rng.choices(keys,k=len(keys)) for c in groups[k]]
        b=statistics.mean(c['outcomes']['PATH-G']['utility'] for c in chosen)
        g=statistics.mean(c['outcomes']['feasible_greedy']['utility'] for c in chosen)
        gains.append((b/g-1)*100)
    gains.sort()
    result={'run_id':'xuemai-r10-20261117-v1','source_commit':read('protocol.json')['source_commit'],
            'local':{name:{k:v for k,v in data.items() if k!='cases'} for name,data in local.items()},
            'real':real,'business':{k:v for k,v in business.items() if k!='results'},
            'tokens':{k:v for k,v in tokens.items() if k!='rows'},
            'path_mean_gain_percent':(beam/greedy-1)*100,'path_cluster_bootstrap_95_percent':[gains[25],gains[974]],
            'repair':read('repair-validation.json'), 'input_business':read('voice-and-models.json'),
            'class_change':change_result,
            'sources':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in DATA.glob('*.json') if f.name not in ['summary.json','manifest.json']}}
    (DATA/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8',newline='\n')
    figures(result)
    macros={'PathCases':path['evaluation_cases'],'PathGraphs':path['independent_graphs'],
            'PathGain':f'{result["path_mean_gain_percent"]:.2f}', 'RealTasks':real['independent_tasks'],
            'RealRequests':tokens['requests'],'RealTokens':tokens['official_prompt_tokens']+tokens['official_completion_tokens'],
            'BusinessPassed':business['passed'],'BusinessCases':business['scenarios']}
    (REPORT/'experiment-numbers.tex').write_text('\n'.join('\\newcommand{\\'+name+'}{'+str(value)+'}' for name,value in macros.items()),encoding='utf8',newline='\n')
    subprocess.run([sys.executable,str(ROOT/'scripts/build_round10_sections.py')],cwd=ROOT,check=True)
    subprocess.run([sys.executable,str(ROOT/'scripts/build_round10_figures.py')],cwd=ROOT,check=True)
    manifest={'experiment_run_id':result['run_id'],'source_commit':result['source_commit'],
              'implementation_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'dataset_version':'r10-v1','configuration':'protocol.json',
              'offline_results':['ktrace.json','path.json','class.json','retrieval.json'],
              'real_results':['protocol.json','end-to-end.json','repair-validation.json','voice-and-models.json'],
              'token_usage':'token-ledger.json','summary':'summary.json',
              'figure_sources':['scripts/build_round10_figures.py','scripts/build_round10_report_data.py'],
              'files':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in DATA.rglob('*') if p.is_file() and p.name!='manifest.json'}}
    (DATA/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8',newline='\n')
    print(json.dumps({'run_id':result['run_id'],'requests':tokens['requests'],
                      'tokens':tokens['charged_or_reserved'],'paired_tasks':real['independent_tasks']},ensure_ascii=False))


if __name__=='__main__':main()
