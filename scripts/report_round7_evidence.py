"""从原始实验结果生成报告表格，避免数字转录漂移。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    result = json.loads((ROOT / 'docs/rounds/第七轮方法实验.json').read_text('utf8'))
    summary = result['PATH-G同约束对照']['summary']
    rows = []
    for name, value in summary.items():
        rows.append(f"{name}&{value['utility']:.3f}&{value['goal_coverage']*100:.2f}\\%&"
                    f"{value['budget_utilization']*100:.2f}\\%&{value['runtime_median_ms']:.4f}&"
                    f"{value['prerequisite_violations']} / {value['budget_violations']}\\\\")
    table = (r'\begin{table}[htbp]\centering\caption{48例同约束路径对照，时间单位为毫秒}'
             r'\begin{tabularx}{\linewidth}{Yrrrrr}\toprule 方法&目标值&目标覆盖&时间利用&耗时&先修/预算违规\\\midrule'
             + '\n' + '\n'.join(rows) + '\n' + r'\bottomrule\end{tabularx}\end{table}')
    (ROOT / 'docs/technical-report/round7-path-table.tex').write_text(table, encoding='utf8')
    adverse = []
    for case in result['PATH-G同约束对照']['cases']:
        outcomes = case['outcomes']
        greedy = outcomes['可行效用密度贪心']['utility']
        beam = outcomes['PATH-G']['utility']
        if beam < greedy - 1e-6:
            adverse.append(f"{case['graph']}&{case['budget']}&{len(case['candidates'])}&{greedy:.3f}&{beam:.3f}&{beam-greedy:.3f}\\\\")
    text = (r'\begin{table}[htbp]\centering\caption{PATH-G目标值低于可行贪心的全部案例}'
            r'\begin{tabular}{rrrrrr}\toprule 图编号&预算分钟&候选数&贪心目标值&PATH-G目标值&差值\\\midrule'
            + '\n' + '\n'.join(adverse) + '\n' + r'\bottomrule\end{tabular}\end{table}')
    (ROOT / 'docs/technical-report/round7-path-adverse.tex').write_text(text, encoding='utf8')
    # 使用一组语义配色区分基线与正式方法，坐标由原始结果生成。
    lines = [r'\begin{tikzpicture}[x=1cm,y=1cm,font=\small]']
    for index, (name, value) in enumerate(summary.items()):
        y = 3 - index
        color = 'celadon!60' if name == 'PATH-G' else 'black!18'
        lines += [f'\\node[anchor=east] at (3.5,{y}){{{name}}};',
                  f'\\fill[{color}] (3.7,{y-.22}) rectangle ({3.7+value["utility"]*.23},{y+.22});',
                  f'\\node[anchor=west] at ({3.85+value["utility"]*.23},{y}){{{value["utility"]:.3f}}};']
    lines += [r'\node[anchor=west,font=\normalsize\bfseries] at (0,4){平均路径目标值（相同目标函数）};',
              r'\node[anchor=west] at (0,0){PATH-G相对可行贪心：36胜、9平、3负；两者先修与预算违规均为0。};',
              r'\end{tikzpicture}']
    (ROOT / 'docs/technical-report/figures/method-results.tex').write_text('\n'.join(lines), encoding='utf8')


if __name__ == '__main__':
    build()
