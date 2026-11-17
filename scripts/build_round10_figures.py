"""从实际计算和明确方法结构生成差异化TikZ图，不调用模型。"""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
FIG=ROOT/'docs/technical-report/figures'
DATA=ROOT/'docs/experiments/round10'
SOURCES={
'actions':r'''\begin{tikzpicture}[x=1cm,y=1cm,font=\small,every node/.style={text=black},>={Stealth[length=1.7mm]}]
\foreach \x/\t in {0.9/学生,4.4/诊断与策略,8/模型与课程工具,11.8/校验与评分}{
\node[align=center] at (\x,4.4){\t};\draw[black!30,dashed](\x,4.1)--(\x,0);}
\draw[->,thick,celadon](.9,3.8)--node[above]{原题、错误与前次反馈}(4.4,3.8);
\draw[->,thick,celadon](4.4,3.05)--node[above]{证据与表征策略}(8,3.05);
\draw[->,thick,celadon](8,2.3)--node[above]{一次生成、引用与动作}(11.8,2.3);
\draw[->,thick,celadon](11.8,1.55)--node[above]{有效理解检查}(.9,1.55);
\draw[->,thick,tea](.9,.8)--node[above]{独立作答进入确定性评分}(11.8,.8);
\draw[->,thick,tea](11.8,.08)--node[below]{未通过时，下一轮转为实验或概念对照}(4.4,.08);
\end{tikzpicture}''',
'teacher-flow':r'''\begin{tikzpicture}[x=1cm,y=1cm,font=\small]
\node[anchor=west,font=\bfseries] at (0,3.6){教学方案的约束矩阵};
\foreach \y/\a/\b/\c in {2.8/课时/活动分钟总和/不超过教师预算,2/对象/群组与候选题/来自授权课程工具,1.2/统计/班级人数与错误/匹配本次查询,.4/写入/编辑与确认/保存为教学资源}{
\fill[rice!50](0,\y-.3)rectangle(2,\y+.3);\node at (1,\y){\a};
\node[anchor=west] at (2.3,\y){\b};\node[anchor=west] at (6.6,\y){\c};
\draw[black!20](0,\y-.4)--(12.2,\y-.4);}
\draw[tea,very thick](12.5,0)--(12.5,3.2);
\node[anchor=west,align=left] at (12.8,1.6){目标\\环节\\群组\\任务};
\end{tikzpicture}''',
'plan-execution':r'''\begin{tikzpicture}[x=1cm,y=1cm,font=\small]
\foreach \x/\label in {0/当次学习,4.7/翌日复测,9.4/第六日复测}{
\fill[pale!45](\x,0)rectangle(\x+4.3,2.6);\draw[celadon!70](\x,2.1)--(\x+4.3,2.1);
\node at (\x+2.15,2.35){\label};}
\node[align=left,anchor=west] at (.2,1.1){计划关联具体题目\\活动事件记录完成\\独立评分更新证据};
\node[align=left,anchor=west] at (4.9,1.1){错误后回到短间隔\\提示成功最多两天\\保留本次质量等级};
\node[align=left,anchor=west] at (9.6,1.1){独立成功后延长\\按难易因子增长\\新作答触发重规划};
\draw[->,celadon,thick](.2,-.4)--(13.5,-.4);\node[fill=white] at (6.9,-.4){学习时间与证据持续积累};
\end{tikzpicture}''',
'retrieval':r'''\begin{tikzpicture}[x=1cm,y=1cm,font=\small]
\node[anchor=west,font=\bfseries] at (0,3.5){同一问题的来源组织};
\foreach \y/\label/\text in {2.7/课程片段/知识定义与正文版本,1.65/会话附件/上传者与课程会话范围,.6/引用快照/标题段落与可打开位置}{
\draw[black!30,fill=pale!30](0,\y-.38)rectangle(7.6,\y+.38);
\node[anchor=west] at (.2,\y){\label};\node[anchor=west] at (2.1,\y){\text};}
\draw[celadon,thick](8.1,.2)--(8.1,3.1);
\node[anchor=west,align=left] at (8.5,2.2){词项与知识关联排序\\顺序语义一致性修正};
\node[anchor=west,align=left] at (8.5,.7){每文档最多2段\\合计5段、5200字符};
\end{tikzpicture}''',
'data':r'''\begin{tikzpicture}[font=\small,entity/.style={draw=celadon!65,fill=pale!25,text width=3.2cm,align=left,inner sep=7pt}]
\node[entity](course) at (0,2.1){\textbf{课程与知识}\\课程ID、知识ID\\章节、先修边};
\node[entity](question) at (4.9,2.1){\textbf{资源与题目}\\所属知识、版本\\答案、量规、状态};
\node[entity](attempt) at (9.8,2.1){\textbf{学生作答}\\题目ID、任务ID\\得分、提示、时间};
\node[entity](task) at (0,-.6){\textbf{教师任务}\\课程、目标学生\\发布时基线};
\node[entity](evidence) at (4.9,-.6){\textbf{证据更新}\\作答ID、权重\\前后状态、更新依据};
\node[entity](state) at (9.8,-.6){\textbf{知识与复习状态}\\学生ID、知识ID\\参数、间隔与时间};
\draw(course)--node[above]{1:N}(question);\draw(question)--node[above]{1:N}(attempt);
\draw(course)--node[left]{1:N}(task);\draw(task)--node[above]{关联}(evidence);
\draw(attempt)--(evidence);\draw(evidence)--node[above]{聚合}(state);\draw(attempt)--node[right]{更新}(state);
\end{tikzpicture}''',
'deployment':r'''\begin{tikzpicture}[x=1cm,y=1cm,font=\small,>={Stealth[length=2mm]}]
\draw[celadon!65,rounded corners=6pt,fill=pale!20](0,0)rectangle(10,3.2);
\node[anchor=west,font=\bfseries] at (.3,2.8){本机应用边界};
\node[align=center](browser)at(1.7,1.6){浏览器工作区\\React与共享主题};
\node[align=center](api)at(5.2,1.6){FastAPI服务\\身份、课程与校验};
\node[draw,ellipse,fill=white,align=center](db)at(8.3,1.6){SQLite\\事件与版本};
\draw[->](browser)--(api);\draw[->](api)--(db);
\node[draw=tea,fill=rice!40,align=center,minimum height=1.2cm](model)at(12.1,1.6){DeepSeek官方API\\生成与用量结算};
\draw[<->,tea,thick](api.south)--++(0,-.7)-|(model.south);
\end{tikzpicture}''',
'intent-control':r'''\begin{tikzpicture}[x=1cm,y=1cm,font=\small]
\draw[celadon,thick](.3,0)--(.3,4);
\foreach \y/\date/\title/\details in {3.5/11月3日/统一课程对象与权限/固定接口后联测并修复种子字段,2/11月12日/知识网络阅读优化/保留九处遮挡后进行几何复核,.5/11月12日/教师混合意图修复/产物任务优先使专项失败转为通过}{
\fill[celadon](.3,\y)circle(.075);\node[anchor=west]at(.65,\y){\date};
\node[anchor=west,font=\bfseries]at(3,\y+.15){\title};\node[anchor=west]at(3,\y-.4){\details};}
\end{tikzpicture}'''
}


def main():
    for name,source in SOURCES.items():(FIG/(name+'.tex')).write_text(source+'\n',encoding='utf8',newline='\n')
    events=json.loads((ROOT/'docs/technical-report/evidence-example.json').read_text('utf8'))
    lines=[r'\begin{tikzpicture}[x=1cm,y=4cm,font=\small]',r'\draw[->](0,0)--(13,0)node[right]{事件};',r'\draw[->](0,0)--(0,.82)node[above]{知识估计};']
    for value in [.25,.5,.75]:
        lines.append(f'\\draw[black!15](0,{value})--(12.3,{value});\\node[left]at(0,{value}){{{value}}};')
    points=[]
    for i,event in enumerate(events):
        x=.5+i*1.9;y=event['value'];points.append(f'({x},{y})')
        label=['先验','独立','提示','错误','订正','重复','30天'][i]
        lines.append(f'\\fill[celadon]({x},{y})circle(.045cm);\\node[below]at({x},0){{{label}}};')
    lines += ['\\draw[celadon,thick] '+'--'.join(points)+';',r'\end{tikzpicture}']
    (FIG/'evidence.tex').write_text('\n'.join(lines),encoding='utf8',newline='\n')
    path=json.loads((DATA/'path.json').read_text('utf8'))
    case=next(c for c in path['cases'] if c['split']=='eval' and len(c['parents'])==6
              and sum(len(parents) for parents in c['parents'].values())>=4 and c['budget']==30)
    plan=case['outcomes']['PATH-G'];costs={c['knowledge_id']:c['estimated_minutes'] for c in case['candidates']}
    lines=[r'\begin{tikzpicture}[x=1cm,y=1cm,font=\small,>={Stealth[length=1.5mm]}]']
    for i,k in enumerate(case['parents']):
        selected=int(k) in plan['sequence'];fill='pale' if selected else 'white'
        lines.append(f'\\node[circle,draw=celadon,fill={fill},minimum size=8mm](n{k})at({i%3*2+.5},{2.8-i//3*1.8}){{$k_{{{k}}}$}};')
    for k,parents in case['parents'].items():
        for p in parents:lines.append(f'\\draw[->](n{p})--(n{k});')
    lines.append(r'\node[anchor=west,font=\bfseries]at(6.6,3.4){30分钟内的实际候选序列};')
    spent=0
    for i,k in enumerate(plan['sequence']):
        width=costs[k]*.19
        lines.append(f'\\fill[pale!80]({6.6+spent*.19},{2.5-i*.01})rectangle({6.6+spent*.19+width},1.6);')
        lines.append(f'\\node at({6.6+spent*.19+width/2},2.05){{$k_{{{k}}}$}};')
        spent+=costs[k]
    lines.append(f'\\node[anchor=west]at(6.6,1){{用时{spent}分钟，效用{plan["utility"]:.2f}}};')
    lines.append(r'\node[anchor=west]at(6.6,.3){先修在前，剩余时间决定后续候选};\end{tikzpicture}')
    (FIG/'path-search.tex').write_text('\n'.join(lines),encoding='utf8',newline='\n')
    data=json.loads((DATA/'class.json').read_text('utf8'));case=data['cases'][6]
    lines=[r'\begin{tikzpicture}[x=.7cm,y=.28cm,font=\small]']
    for j,title in enumerate(['概念','步骤','推理','迁移','提示','参与']):lines.append(f'\\node[rotate=0]at({j*1.35+1},1.3){{{title}}};')
    for i,student in enumerate(case['students'][:12]):
        lines.append(f'\\node[anchor=east]at(0,{-i-0.5}){{$s_{{{student["id"]}}}$}};')
        for j,value in enumerate(student['features']):
            lines.append(f'\\fill[celadon!{max(3,int(value*85))}]({j*1.35+.4},{-i})rectangle({j*1.35+1.6},{-i-1});')
    for i,group in enumerate(case['groups'][:4]):
        lines.append(f'\\node[anchor=west,align=left]at(9,{-i*3-1}){{{group["focus"]}\\\\对应知识{group["knowledge_id"]}，候选题{group["question_ids"][0]}}};')
    lines.append(r'\end{tikzpicture}')
    (FIG/'class-loop.tex').write_text('\n'.join(lines),encoding='utf8',newline='\n')
    print('已生成10种方法图形，时间线、序列图、矩阵、网络、热图、日历与实体关联')


if __name__=='__main__':main()
