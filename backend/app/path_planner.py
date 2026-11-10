"""PATH-G：预算内的先修约束束搜索。候选动作必须有可执行资源。"""
from __future__ import annotations


def plan_path(candidates, parents, states, budget=30, beam_width=24):
    """返回计划与可复算分项；已安排先修表示顺序约束，不表示已经掌握。"""
    by_id = {c['knowledge_id']: c for c in candidates}
    ready = {k for k, s in states.items() if s['effective_count'] >= 2 and s['value'] >= .6}
    utility = {}
    for kid, c in by_id.items():
        s = states[kid]
        parts = {'need': 4 * (1 - s['value']), 'uncertainty': 1.5 * (s['upper'] - s['lower']),
                 'goal': 3 * bool(c.get('goal')), 'teacher': 3 * bool(c.get('teacher_task')),
                 'due': 2 * bool(c.get('due')), 'mistakes': min(3, c.get('wrong', 0))}
        utility[kid] = parts
    # (路径, 分钟, 效用)。固定宽度限制开销，按知识ID破除相同分值。
    beam = [((), 0, 0.)]
    best = beam[0]
    expanded = 0
    for _ in range(min(len(by_id), max(1, budget // 4))):
        next_beam = []
        for path, cost, score in beam:
            for kid, c in by_id.items():
                minutes = max(4, c.get('estimated_minutes', 8))
                if kid in path or cost + minutes > budget:
                    continue
                if any(p not in ready and p not in path for p in parents.get(kid, [])):
                    continue
                # 后续步骤折扣；单位时间效用与覆盖增益兼顾。
                gain = sum(utility[kid].values()) * (.92 ** len(path)) - .06 * minutes
                candidate = (path + (kid,), cost + minutes, score + gain)
                next_beam.append(candidate)
                expanded += 1
                if (candidate[2], -candidate[1], candidate[0]) > (best[2], -best[1], best[0]):
                    best = candidate
        if not next_beam:
            break
        beam = sorted(next_beam, key=lambda b: (-b[2], b[1], b[0]))[:beam_width]
    return {'method': 'PATH-G', 'knowledge_ids': list(best[0]), 'minutes': best[1],
            'utility': round(best[2], 4), 'components': utility, 'budget': budget,
            'expanded': expanded, 'beam_width': beam_width}


def order_recommendations(candidates, parents, states, budget=30):
    plan = plan_path(candidates, parents, states, budget)
    ordered = list(plan['knowledge_ids'])
    remaining = {c['knowledge_id']: c for c in candidates if c['knowledge_id'] not in ordered}
    ready = {k for k, s in states.items() if s['effective_count'] >= 2 and s['value'] >= .6}
    while remaining:
        eligible = [k for k in remaining if all(p in ready or p in ordered or p not in remaining for p in parents.get(k, []))]
        if not eligible:  # 数据层有环路校验；异常导入也保证终止。
            eligible = list(remaining)
        kid = max(eligible, key=lambda k: (sum(plan['components'][k].values()), -k))
        ordered.append(kid)
        remaining.pop(kid)
    by_id = {c['knowledge_id']: c for c in candidates}
    return [by_id[k] | {'priority': len(ordered) - i, 'in_current_plan': k in plan['knowledge_ids'],
                       'path_position': i + 1, 'path_plan': plan,
                       'utility_components': plan['components'][k]} for i, k in enumerate(ordered)]
