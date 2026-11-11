"""普通初始化数据库的课程覆盖检查，不创建或修改教学数据。"""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.db import get_db


def inspect(db):
    output=[]
    primary=db.execute("SELECT id FROM users WHERE username='student1'").fetchone()[0]
    for c in db.execute("SELECT * FROM courses WHERE code IN ('CS201','CS101') ORDER BY code"):
        cid=c['id'];one=lambda sql,*args:db.execute(sql,(cid,*args)).fetchone()[0]
        data={'course_id':cid,'code':c['code'],'title':c['title'],
          'chapters':one('SELECT COUNT(*) FROM chapters WHERE course_id=?'),
          'knowledge':one('SELECT COUNT(*) FROM knowledge_points WHERE course_id=?'),
          'edges':one('SELECT COUNT(*) FROM knowledge_edges WHERE course_id=?'),
          'questions':one("SELECT COUNT(*) FROM questions WHERE course_id=? AND status='approved'"),
          'question_types':dict(db.execute("SELECT type,COUNT(*) FROM questions WHERE course_id=? AND status='approved' GROUP BY type",(cid,))),
          'resources':dict(db.execute('SELECT kind,COUNT(*) FROM resources WHERE course_id=? GROUP BY kind',(cid,))),
          'assignments':one('SELECT COUNT(*) FROM assignments WHERE course_id=?'),
          'goals':one('SELECT COUNT(*) FROM learning_goals WHERE course_id=? AND student_id=?',primary),
          'plans':one('SELECT COUNT(*) FROM study_plans WHERE course_id=? AND student_id=?',primary),
          'attempts':one('SELECT COUNT(*) FROM attempts a JOIN questions q ON q.id=a.question_id WHERE q.course_id=? AND a.student_id=?',primary),
          'mistakes':one('SELECT COUNT(*) FROM mistakes m JOIN questions q ON q.id=m.question_id WHERE q.course_id=? AND m.student_id=?',primary),
          'conversations':one('SELECT COUNT(*) FROM ai_conversations WHERE course_id=? AND user_id=?',primary),
          'classroom':one('SELECT COUNT(*) FROM classroom WHERE course_id=?'),
          'responses':one('SELECT COUNT(*) FROM classroom_responses r JOIN classroom c ON c.id=r.activity_id WHERE c.course_id=?'),
          'notes':one('SELECT COUNT(*) FROM notes WHERE course_id=? AND student_id=?',primary),
          'experiments':one("SELECT COUNT(*) FROM learning_events WHERE course_id=? AND student_id=? AND kind='experiment'",primary),
          'students':one('SELECT COUNT(DISTINCT student_id) FROM class_members m JOIN classes c ON c.id=m.class_id WHERE c.course_id=?'),
          'invalid_relations':one('SELECT COUNT(*) FROM knowledge_edges e LEFT JOIN knowledge_points s ON s.id=e.source LEFT JOIN knowledge_points t ON t.id=e.target WHERE e.course_id=? AND (s.course_id!=e.course_id OR t.course_id!=e.course_id OR s.id IS NULL OR t.id IS NULL)'),
          'attempts_before_publication':one('SELECT COUNT(*) FROM attempts a JOIN assignments t ON t.id=a.assignment_id WHERE t.course_id=? AND julianday(a.created_at)<julianday(t.created_at)')}
        checks={'chapters':data['chapters']>=5,'knowledge':25<=data['knowledge']<=50,'questions':data['questions']>=30,'types':len(data['question_types'])>=5,'videos':data['resources'].get('video',0)>=3,'goals':data['goals']>=3,'plans':data['plans']>=10,'history':data['conversations']>=4,'classroom':data['classroom']>=4 and data['responses']>=10,'integrity':not(data['invalid_relations'] or data['attempts_before_publication'])}
        data['checks']=checks;data['passed']=all(checks.values());output.append(data)
    return {'courses':output,'passed':len(output)==2 and all(c['passed'] for c in output),'foreign_key_errors':[list(r) for r in db.execute('PRAGMA foreign_key_check')],'sample_packages':[dict(r) for r in db.execute('SELECT * FROM sample_packages')]}


if __name__=='__main__':
    with get_db() as db:result=inspect(db)
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if len(sys.argv)>1:Path(sys.argv[1]).write_text(text,encoding='utf-8')
    print(text)
    sys.exit(0 if result['passed'] and not result['foreign_key_errors'] else 1)
