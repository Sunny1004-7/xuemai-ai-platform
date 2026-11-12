"""固定种子的方法对照与师生业务验证，全部使用本地Mock。"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_db
from backend.app.evidence import estimate_state
from backend.app.path_planner import plan_path
from backend.app.learning_insights import dynamic_groups
from backend.app.retrieval import retrieve
from backend.app.teacher_assistant import validate_draft, finalize_teacher, TEACH_MARKER
from backend.app.ai_routes import ChatInput
from scripts.validate_round4_methods import ktrace, pathg, classloop, diaguide

SEED = 7011
NOW = datetime(2026, 11, 12, tzinfo=timezone.utc)


def constrained_greedy(candidates, parents, states, budget, components):
    ready = {key for key, state in states.items() if state['effective_count'] >= 2 and state['value'] >= .6}
    remaining = {item['knowledge_id']: item for item in candidates}
    selected, minutes = [], 0
    while remaining:
        available = [key for key, item in remaining.items()
                     if minutes + item['estimated_minutes'] <= budget
                     and all(parent in ready or parent in selected for parent in parents.get(key, []))]
        if not available:
            break
        def marginal(key):
            cost = remaining[key]['estimated_minutes']
            return (sum(components[key].values()) * .92 ** len(selected) - .06 * cost) / cost
        key = max(available, key=lambda item: (marginal(item), -item))
        selected.append(key)
        minutes += remaining.pop(key)['estimated_minutes']
    return selected


def path_comparison():
    rng = random.Random(SEED)
    cases = []
    for graph in range(12):
        count = 8 + graph % 3 * 4
        parents = {key: [parent for parent in range(1, key) if rng.random() < .16] for key in range(1, count + 1)}
        states = {key: estimate_state(now=NOW) for key in parents}
        for key in states:
            if rng.random() < .15:
                states[key] |= {'value': .8, 'effective_count': 4}
        goals = set(rng.sample(list(parents), 3))
        candidates = [{'knowledge_id': key, 'estimated_minutes': rng.choice([3, 5, 8, 12]),
                       'goal': key in goals, 'teacher_task': rng.random() < .15,
                       'due': rng.random() < .2, 'wrong': rng.randrange(4)} for key in parents]
        costs = {item['knowledge_id']: item['estimated_minutes'] for item in candidates}
        for budget in [10, 20, 30, 45]:
            plan = plan_path(candidates, parents, states, budget)
            components = plan['components']
            def static():
                result, spent = [], 0
                for item in sorted(candidates, key=lambda row: (not row['goal'], row['knowledge_id'])):
                    if spent + item['estimated_minutes'] <= budget:
                        result.append(item['knowledge_id']); spent += item['estimated_minutes']
                return result
            methods = {
                '目标优先排序': static,
                '可行效用密度贪心': lambda: constrained_greedy(candidates, parents, states, budget, components),
                'PATH-G': lambda: plan_path(candidates, parents, states, budget)['knowledge_ids'],
            }
            outcomes = {}
            for name, function in methods.items():
                timings = []
                for _ in range(3):
                    begin = time.perf_counter_ns(); sequence = function()
                    timings.append((time.perf_counter_ns() - begin) / 1e6)
                ready = {key for key, state in states.items() if state['effective_count'] >= 2 and state['value'] >= .6}
                seen, violations = set(ready), 0
                for key in sequence:
                    violations += sum(parent not in seen for parent in parents[key]); seen.add(key)
                used = sum(costs[key] for key in sequence)
                utility = sum(sum(components[key].values()) * .92 ** index - .06 * costs[key]
                              for index, key in enumerate(sequence))
                outcomes[name] = {'sequence': sequence, 'prerequisite_violations': violations,
                                  'budget_violation': used > budget, 'minutes': used,
                                  'budget_utilization': used / budget, 'goal_coverage': len(goals & set(sequence)) / len(goals),
                                  'utility': round(utility, 6), 'runtime_median_ms': round(statistics.median(timings), 4)}
            assert all(not outcomes[name]['budget_violation'] and not outcomes[name]['prerequisite_violations']
                       for name in ['可行效用密度贪心', 'PATH-G'])
            cases.append({'graph': graph, 'budget': budget, 'candidates': candidates, 'parents': parents,
                          'states': states, 'outcomes': outcomes})
    summary = {}
    for name in cases[0]['outcomes']:
        rows = [case['outcomes'][name] for case in cases]
        summary[name] = {key: round(statistics.mean(row[key] for row in rows), 6)
                         for key in ['utility', 'goal_coverage', 'budget_utilization', 'runtime_median_ms']}
        summary[name]['prerequisite_violations'] = sum(row['prerequisite_violations'] for row in rows)
        summary[name]['budget_violations'] = sum(row['budget_violation'] for row in rows)
    differences = [case['outcomes']['PATH-G']['utility'] - case['outcomes']['可行效用密度贪心']['utility'] for case in cases]
    return {'seed': SEED, 'cases': cases, 'summary': summary,
            'beam_vs_greedy': {'wins': sum(value > 1e-5 for value in differences),
                               'ties': sum(abs(value) <= 1e-5 for value in differences),
                               'losses': sum(value < -1e-5 for value in differences)},
            'objective': '相同候选、效用、先修与时间预算，贪心逐步选择可行候选的边际效用/分钟，束宽24'}


def membership(groups):
    return {frozenset(group['student_ids']) for group in groups}


def pair_agreement(first, second):
    def label(groups):
        return {student: index for index, group in enumerate(groups) for student in group['student_ids']}
    left, right = label(first), label(second)
    ids = sorted(left)
    pairs = [(a, b) for index, a in enumerate(ids) for b in ids[index + 1:]]
    return sum((left[a] == left[b]) == (right[a] == right[b]) for a, b in pairs) / len(pairs)


def group_robustness():
    rng = random.Random(SEED)
    questions = [{'id': topic * 10 + skill + 1, 'knowledge_id': topic + 1,
                  'skill': name, 'difficulty': 2} for topic in range(4)
                 for skill, name in enumerate(['concept', 'procedure', 'reasoning', 'transfer'])]
    base = []
    for index in range(24):
        vector = [.12] * 4 + [.1, .1]; vector[index % 4] = .88
        base.append({'id': index + 1, 'features': vector, 'recent_graded_count': 20,
                     'feature_confidence': [1] * 6, 'weak_knowledge_ids': [index % 4 + 1]})
    scenarios = {'四类原型': deepcopy(base)}
    noisy = deepcopy(base)
    for student in noisy:
        student['features'] = [max(0, min(1, value + rng.gauss(0, .06))) for value in student['features']]
    scenarios['观测噪声'] = noisy
    mixed = deepcopy(noisy)
    for index in range(4):
        values = [.15] * 4 + [.3, .2]
        values[index] = .7; values[(index + 1) % 4] = .65
        mixed.append({'id': 25 + index, 'features': values, 'recent_graded_count': 5,
                      'feature_confidence': [.5] * 6, 'weak_knowledge_ids': [index + 1, (index + 1) % 4 + 1]})
    for index in range(3):
        mixed.append({'id': 29 + index, 'features': [.5] * 6, 'recent_graded_count': index % 2,
                      'feature_confidence': [0] * 6, 'weak_knowledge_ids': []})
    scenarios['混合困难与稀疏观测'] = mixed
    missing = deepcopy(noisy); missing[0]['feature_confidence'][0] = 0; missing[0]['features'][0] = .01
    scenarios['缺失维度低值'] = deepcopy(missing)
    missing[0]['features'][0] = .99
    scenarios['缺失维度高值'] = missing
    changed = deepcopy(base); changed[0]['features'] = base[1]['features'].copy(); changed[0]['weak_knowledge_ids'] = [2]
    scenarios['近期困难变化'] = changed
    results = []
    for name, students in scenarios.items():
        groups = dynamic_groups(students, questions)
        shuffled = students.copy(); rng.shuffle(shuffled)
        without_support = dynamic_groups([student | {'feature_confidence': [1] * 6} for student in students], questions)
        expected_observation = {student['id'] for student in students if student['recent_graded_count'] < 2}
        actual_observation = {sid for group in groups if group.get('evidence_level') == '观察中' for sid in group['student_ids']}
        valid_questions = {question['id'] for question in questions}
        assert expected_observation == actual_observation
        assert membership(groups) == membership(dynamic_groups(shuffled, questions))
        assert all(set(group['question_ids']) <= valid_questions for group in groups)
        task_checks = []
        for group in groups:
            weak = Counter(kid for student in students if student['id'] in group['student_ids'] for kid in student['weak_knowledge_ids'])
            if not weak:
                continue
            expected_topics = {key for key, value in weak.items() if value == max(weak.values())}
            selected_topic = next(question['knowledge_id'] for question in questions if question['id'] == group['question_ids'][0])
            task_checks.append({'group': group['id'], 'expected_topics': sorted(expected_topics), 'selected_topic': selected_topic, 'matched': selected_topic in expected_topics})
        assert all(item['matched'] for item in task_checks)
        results.append({'name': name, 'students': students, 'groups': groups, 'without_support': without_support,
                        'task_matching': task_checks,
                        'permutation_stable': True, 'observation_students': sorted(actual_observation),
                        'support_ablation_pair_agreement': pair_agreement(groups, without_support),
                        'student1_focus': next(group['focus'] for group in groups if 1 in group['student_ids'])})
    low, high = results[3], results[4]
    return {'seed': SEED, 'cases': results, 'missing_dimension_membership_stable': membership(low['groups']) == membership(high['groups']),
            'missing_dimension_without_support_agreement': pair_agreement(low['without_support'], high['without_support']),
            'noise_pair_agreement': pair_agreement(results[0]['groups'], results[1]['groups'])}


def login(client, username):
    response = client.post('/api/auth/login', json={'username': username, 'password': 'Xuemai123!'})
    response.raise_for_status()
    return {'Authorization': 'Bearer ' + response.json()['token']}


def ask(client, headers, **request):
    response = client.post('/api/ai/chat', headers=headers, json=request)
    response.raise_for_status()
    data = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
    return next(item for item in reversed(data) if item.get('status') == 'complete')


def teacher_checks(client, teacher):
    checks = []
    simple = ask(client, teacher, course_id=1, message='比较栈与队列的课堂提问建议。')
    checks.append({'name': '轻量研讨路由', 'passed': simple['teaching']['task'] == 'discussion' and not simple['teaching']['evidence']})
    request = ChatInput(course_id=1, class_id=1, knowledge_id=2,
                        message='请基于这个班栈与队列的错误，设计一节30分钟讲评课。')
    done = ask(client, teacher, **request.model_dump())
    plan, artifact = done['teaching'], done['artifact']
    checks.append({'name': '证据与设计混合意图', 'passed': plan['task'] == 'design' and bool(artifact.get('id')), 'actual_task': plan['task']})
    if not artifact.get('id'):
        return {'checks': checks, 'passed': False}
    payload = artifact['draft']
    with get_db() as db:
        teacher_user = dict(db.execute("SELECT * FROM users WHERE username='teacher'").fetchone())
        topic_ids = {row[0] for row in db.execute("SELECT id FROM knowledge_points WHERE course_id=1 AND (title LIKE '%栈%' OR title LIKE '%队列%')")}
        members = {row[0] for row in db.execute('SELECT student_id FROM class_members WHERE class_id=1')}
        expected = Counter(row['error_type'] for row in db.execute('SELECT a.student_id,a.error_type,q.knowledge_id FROM attempts a JOIN questions q ON q.id=a.question_id WHERE q.course_id=1 AND a.correct=0') if row['student_id'] in members and row['knowledge_id'] in topic_ids)
        actual = {item['name']: item['value'] for item in plan['evidence']['errors']}
        checks.append({'name': '栈队列专题证据范围', 'passed': actual == dict(expected), 'expected': dict(expected), 'actual': actual})
        mutations = [('超时安排拒绝', {'steps': [{'title': '长活动', 'minutes': 80, 'activity': '逐步分析结构'}]}),
                     ('未知群组拒绝', {'groups': [{'group_id': 'unknown', 'objective': '复测检查', 'question_ids': [1]}]}),
                     ('跨候选题目拒绝', {'groups': [{'group_id': payload['groups'][0]['group_id'], 'objective': '复测检查', 'question_ids': [999999]}]})]
        for name, mutation in mutations:
            rejected = False
            try:
                validate_draft(db, request, plan, payload | mutation)
            except ValueError:
                rejected = True
            checks.append({'name': name, 'passed': rejected})
        text, checked, _ = finalize_teacher(db, teacher_user, request, deepcopy(plan), '这个班有991位学生。' + TEACH_MARKER + json.dumps(payload, ensure_ascii=False) + '-->', [])
        checks.append({'name': '无来源统计移除', 'passed': '991' not in text and checked['numeric_validation']['unsupported'] == ['991']})
    edited = deepcopy(payload); edited['title'] = '栈与队列专项验证教案'
    route = f"/api/ai/teacher-drafts/{artifact['id']}/save"
    first = client.post(route, headers=teacher, json=edited); second = client.post(route, headers=teacher, json=edited)
    checks.append({'name': '编辑保存与幂等', 'passed': first.status_code == 200 and second.status_code == 200 and first.json()['resource_id'] == second.json()['resource_id']})
    checks.append({'name': '学生隔离教师草稿', 'passed': client.get(f"/api/ai/teacher-drafts/{artifact['id']}", headers=login(client, 'student1')).status_code == 404})
    group = next((item for item in payload['groups'] if 2 in item['student_ids']), payload['groups'][0])
    assignment = client.post('/api/assignments', headers=teacher, json={'course_id': 1, 'class_id': 1, 'title': '栈队列专项复测', 'description': group['objective'], 'question_ids': group['question_ids'], 'student_ids': group['student_ids']})
    assignment.raise_for_status(); aid = assignment.json()['id']
    with get_db() as db:
        student_id = group['student_ids'][0]
        username = db.execute('SELECT username FROM users WHERE id=?', (student_id,)).fetchone()[0]
        answers = [(qid, json.loads(db.execute('SELECT answer FROM questions WHERE id=?', (qid,)).fetchone()[0])) for qid in group['question_ids']]
    student = login(client, username)
    attempts = [client.post('/api/attempts', headers=student, json={'question_id': qid, 'assignment_id': aid, 'answer': answer}) for qid, answer in answers]
    result = client.get(f'/api/assignments/{aid}/results', headers=teacher)
    result.raise_for_status()
    student_result = next(item for item in result.json() if item['id'] == student_id)
    checks.append({'name': '发布后学生完成与教师结果', 'passed': all(item.status_code == 201 for item in attempts) and student_result['completed'] and student_result['completed_count'] == len(answers), 'assignment_id': aid, 'student_id': student_id, 'questions': group['question_ids'], 'results': result.json()})
    return {'checks': checks, 'passed': all(item['passed'] for item in checks), 'generated_artifact': artifact,
            'api_success': True, 'structure_valid': True, 'teaching_requirement_met': plan['task'] == 'design', 'model_calls': 0}


def retrieval_extensions(client, teacher):
    student = login(client, 'student1')
    upload = client.post('/api/ai/attachments', headers=student, data={'course_id': 1}, files={'file': ('队列笔记.md', '队列保持先进先出，先入队的元素先出队。'.encode(), 'text/markdown')})
    upload.raise_for_status(); attachment_id = upload.json()['id']
    queries = [
        ('同义表达', '先放入的元素先取出，用于按到达先后处理', 2),
        ('未提供知识点', '队列先进先出', None),
        ('不同资料片段', '循环队列如何判断队满和队空', 0),
        ('课程与附件相似', '队列先进先出', 2),
        ('证据不足', '火星交通信号量子跃迁折叠规律', None),
    ]
    cases = []
    with get_db() as db:
        actual_queue = db.execute("SELECT id FROM knowledge_points WHERE course_id=1 AND title LIKE '%循环队列%' LIMIT 1").fetchone()[0]
        for name, query, point in queries:
            kid = actual_queue if point == 0 else point
            results = retrieve(db, 1, query, kid, user={'id': 2, 'role': 'student'}, attachment_ids=[attachment_id] if name == '课程与附件相似' else [])
            cases.append({'name': name, 'query': query, 'knowledge_id': kid, 'results': results,
                          'top3_titles': [item['title'] for item in results[:3]], 'empty': not results,
                          'valid_locators': all(item.get('locator') and item.get('version') for item in results),
                          'attachment_returned': any(item['source_kind'] == 'attachment' for item in results)})
    return {'name': '知识上下文消歧的扩展场景检查', 'cases': cases, 'model_requests': 0}


def controlled_disambiguation():
    cases = []
    with get_db() as db:
        for course_id in (1, 2):
            for point in db.execute('SELECT id,title FROM knowledge_points WHERE course_id=? ORDER BY id LIMIT 10', (course_id,)).fetchall():
                query = '请结合当前知识点，说明边界条件与操作步骤'
                expected = {row[0] for row in db.execute('SELECT id FROM resources WHERE course_id=? AND knowledge_id=?', (course_id, point['id']))}
                results = {}
                for boost in (False, True):
                    citations = retrieve(db, course_id, query, point['id'], user={'id': 2, 'role': 'student'}, knowledge_boost=boost)
                    results['知识关联' if boost else '词项排序'] = {'top1': bool(citations and citations[0].get('resource_id') in expected),
                        'top3': any(item.get('resource_id') in expected for item in citations[:3]), 'citations': citations}
                cases.append({'course_id': course_id, 'knowledge_id': point['id'], 'query': query, 'expected_resource_ids': sorted(expected), 'results': results})
    return {'name': '受控同词歧义场景下的知识上下文消歧实验', 'cases': cases,
            'summary': {name: {metric: sum(case['results'][name][metric] for case in cases) for metric in ['top1', 'top3']} for name in ['词项排序', '知识关联']},
            'conditions': '同一查询、当前知识与候选片段，仅切换关联加权，20例跨两课'}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', default='docs/rounds/第七轮方法实验.json'); args = parser.parse_args()
    report = {'seed': SEED, 'fixed_algorithm_time': NOW.isoformat(), 'executed_at': datetime.now(timezone.utc).isoformat(),
              'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'command': '.venv/Scripts/python.exe scripts/validate_round7_methods.py', 'real_model_calls': 0,
              'K-TRACE': ktrace(), 'PATH-G原对照': pathg(), 'PATH-G同约束对照': path_comparison(),
              'CLASS-LOOP原型': classloop(), 'CLASS-LOOP鲁棒性': group_robustness()}
    with tempfile.TemporaryDirectory(prefix='xuemai-round7-') as directory:
        os.environ.update(DATABASE_PATH=str(Path(directory) / 'methods.db'), AI_MODE='mock', XUEMAI_DEMO_COHORT='1', AI_REQUESTS_PER_MINUTE='100')
        with TestClient(app) as client:
            teacher, student = login(client, 'teacher'), login(client, 'student1')
            report['检索控制'] = controlled_disambiguation()
            report['DIA-GUIDE'] = diaguide(client, student)
            report['DIA-TEACH'] = teacher_checks(client, teacher)
            report['检索扩展'] = retrieval_extensions(client, teacher)
    target = ROOT / args.output
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf8')
    print(json.dumps({'PATH-G': report['PATH-G同约束对照']['summary'], 'beam_vs_greedy': report['PATH-G同约束对照']['beam_vs_greedy'],
                      'CLASS-LOOP': {key: value for key, value in report['CLASS-LOOP鲁棒性'].items() if key != 'cases'},
                      'DIA-TEACH': [{'name': item['name'], 'passed': item['passed']} for item in report['DIA-TEACH']['checks']]}, ensure_ascii=False, indent=2))
    if not report['DIA-TEACH']['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
