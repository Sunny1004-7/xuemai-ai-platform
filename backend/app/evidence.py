"""带时间折减的Beta证据模型及SM-2间隔调度。所有参数显式保存。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math

PRIOR_ALPHA = 1.0
PRIOR_BETA = 3.0
HALF_LIFE_DAYS = 30.0


def utc_now():
    return datetime.now(timezone.utc)


def parse_time(value):
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def estimate_state(row=None, now=None):
    now = now or utc_now()
    item = dict(row) if row else {}
    days = max(0, (now - parse_time(item['updated_at'])).total_seconds() / 86400) if item.get('updated_at') else 0
    retention = 2 ** (-days / HALF_LIFE_DAYS)
    # 旧记录作为两条弱先验证据迁入，原始学习事件仍保留。
    alpha = item.get('alpha')
    beta = item.get('beta')
    if alpha is None or beta is None:
        value = item.get('value', .25)
        alpha = PRIOR_ALPHA + value * 2 if row else PRIOR_ALPHA
        beta = PRIOR_BETA + (1 - value) * 2 if row else PRIOR_BETA
    alpha = PRIOR_ALPHA + (alpha - PRIOR_ALPHA) * retention
    beta = PRIOR_BETA + (beta - PRIOR_BETA) * retention
    value = alpha / (alpha + beta)
    count = float(item.get('effective_count') or 0) * retention
    deviation = math.sqrt(alpha * beta / ((alpha + beta) ** 2 * (alpha + beta + 1)))
    return {'value': value, 'alpha': alpha, 'beta': beta, 'effective_count': count,
            'lower': max(0, value - 1.96 * deviation), 'upper': min(1, value + 1.96 * deviation),
            'sufficiency': '证据较充分' if count >= 6 else '证据积累中' if count >= 2 else '待补充证据',
            'retention': retention, 'days_since_evidence': round(days, 2), 'model': 'decayed-beta-v2'}


def update_state(state, correct, difficulty, hints, previous=None, now=None):
    now = now or utc_now()
    gap = (now - parse_time(previous['created_at'])).total_seconds() / 86400 if previous else None
    novelty = 1.0
    if previous and gap < 1:
        novelty = 0.0 if correct and previous['correct'] else .35
    weight = (1.0, 1.4, 1.8)[difficulty - 1] * novelty
    quality = 1 / (1 + hints) if correct else 0.0
    alpha = state['alpha'] + weight * quality
    beta = state['beta'] + weight * (1 - quality)
    return {'alpha': alpha, 'beta': beta, 'value': alpha / (alpha + beta),
            'effective_count': state['effective_count'] + weight, 'weight': weight, 'quality': quality,
            'parameters': {'prior_alpha': PRIOR_ALPHA, 'prior_beta': PRIOR_BETA,
                           'half_life_days': HALF_LIFE_DAYS, 'difficulty': difficulty,
                           'hint_count': hints, 'novelty': novelty, 'gap_days': gap}}


def schedule_review(previous, correct, hints, repeated, now=None):
    now = now or utc_now()
    old = dict(previous) if previous else {}
    quality = 5 if correct and not hints else 3 if correct else 1
    ease = max(1.3, float(old.get('ease', 2.5)) + .1 - (5-quality) * (.08 + (5-quality) * .02))
    repetitions = int(old.get('repetitions', 0)) + 1 if quality >= 3 else 0
    interval = 1 if repetitions <= 1 else 6 if repetitions == 2 else round(float(old.get('interval_days', 1)) * ease, 2)
    if hints:
        interval = min(interval, 2)
    if repeated and old:
        return old
    return {'interval_days': interval, 'ease': ease, 'repetitions': repetitions,
            'last_quality': quality, 'next_due': (now + timedelta(days=interval)).isoformat(),
            'updated_at': now.isoformat()}


def knowledge_state(db, student_id, knowledge_id, now=None):
    row = db.execute('SELECT * FROM mastery WHERE student_id=? AND knowledge_id=?', (student_id, knowledge_id)).fetchone()
    return estimate_state(row, now)


def apply_evidence(db, user_id, question, attempt_id, correct, hints, previous=None):
    state = knowledge_state(db, user_id, question['knowledge_id'])
    update = update_state(state, correct, question['difficulty'], hints, previous)
    level = 'transfer' if correct and not hints and question['difficulty'] == 3 else 'independent' if correct and not hints else 'assisted' if correct else 'developing'
    # 零权重重复成功不刷新时钟，避免借重复作答阻止时间折减。
    if update['weight'] > 0:
        db.execute('''INSERT INTO mastery(student_id,knowledge_id,value,evidence_count,level,alpha,beta,effective_count)
                  VALUES(?,?,?,1,?,?,?,?) ON CONFLICT(student_id,knowledge_id) DO UPDATE SET
                  value=excluded.value,evidence_count=mastery.evidence_count+1,level=excluded.level,
                  alpha=excluded.alpha,beta=excluded.beta,effective_count=excluded.effective_count,updated_at=CURRENT_TIMESTAMP''',
                   (user_id, question['knowledge_id'], update['value'], level, update['alpha'], update['beta'], update['effective_count']))
    details = {'model': 'decayed-beta-v2', **update['parameters'], 'correct': bool(correct),
               'level': level, 'source': 'teacher_review' if question['type'] in ('short', 'step') else 'automatic'}
    db.execute('''INSERT INTO evidence_updates(attempt_id,student_id,knowledge_id,before_value,after_value,weight,quality,details)
                  VALUES(?,?,?,?,?,?,?,?)''', (attempt_id, user_id, question['knowledge_id'], state['value'], update['value'], update['weight'], update['quality'], json.dumps(details, ensure_ascii=False)))
    previous_schedule = db.execute('SELECT * FROM review_schedule WHERE student_id=? AND question_id=?', (user_id, question['id'])).fetchone()
    schedule = schedule_review(previous_schedule, correct, hints, update['weight'] == 0)
    db.execute('''INSERT INTO review_schedule(student_id,question_id,interval_days,ease,repetitions,last_quality,next_due,updated_at)
                  VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(student_id,question_id) DO UPDATE SET
                  interval_days=excluded.interval_days,ease=excluded.ease,repetitions=excluded.repetitions,
                  last_quality=excluded.last_quality,next_due=excluded.next_due,updated_at=excluded.updated_at''',
               (user_id, question['id'], schedule['interval_days'], schedule['ease'], schedule['repetitions'], schedule['last_quality'], schedule['next_due'], schedule['updated_at']))
    return update, schedule


def diagnose_error(db, user_id, question, answer):
    mapping = json.loads(question['diagnostic_map'] or '{}')
    key = json.dumps(answer, ensure_ascii=False) if isinstance(answer, list) else str(answer)
    if key in mapping:
        return mapping[key]
    weak = db.execute('SELECT source FROM knowledge_edges WHERE target=?', (question['knowledge_id'],)).fetchall()
    if any(knowledge_state(db, user_id, row['source'])['value'] < .4 for row in weak):
        return '先修知识待巩固'
    return {'procedure': '程序步骤偏差', 'reasoning': '推理依据不足', 'transfer': '迁移应用待检验'}.get(question['skill'], '错因待确认')
