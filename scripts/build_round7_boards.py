"""从已保存协作原文、Git对象与实际验证生成演示证据画板。"""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/demo/第七轮演示源'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf8')


def log(name):
    return (ROOT / '.local' / name).read_text('utf8', errors='replace').replace(str(ROOT), '工程根目录')


def build():
    OUT.mkdir(exist_ok=True, parents=True)
    original = (ROOT / 'docs/development-process/004-核心功能实际协作逐字转存.md').read_text('utf8')
    quote = original.split('### 实际起始 Prompt')[1].split('> ')[1].split('\n\n')[0]
    feedback = original.split('### 实际修复反馈')[1].split('> ')[1].split('\n\n')[0]
    fixed = original.split('### 实际结果')[1].split('> ')[1].split('\n\n')[0]
    result = json.loads((ROOT / 'docs/rounds/第七轮方法实验.json').read_text('utf8'))
    old_graph = json.loads((ROOT / 'docs/development-process/第六轮知识网络初次几何结果.json').read_text('utf8'))
    new_graph = json.loads((ROOT / 'docs/rounds/第六轮知识网络几何验证.json').read_text('utf8'))
    stages = []

    def add(chain, stage, title, text, source, date, code=False):
        stages.append(dict(chain=chain, stage=stage, title=title, text=text, source=source, date=date, code=code, duration=7.5))

    add('课程对象与权限', '原始协作指令', '同一课程对象贯通三层实现', quote[:650], '004-核心功能实际协作逐字转存.md / 根代理→后端代理原文节选', '2026-11-03')
    add('课程对象与权限', 'Codex实现反馈', '接口契约先行', original.split('### 实际反馈')[1].split('> ')[1].split('\n\n')[0], '004记录 / 后端代理→根代理', '2026-11-03')
    add('课程对象与权限', '实际联测问题', '初始化阻断AI路由测试', feedback, '004记录 / AI代理实际联测反馈', '2026-11-03')
    add('课程对象与权限', '修复差异', '字段与占位符数量一致', fixed, '004记录 / 后端代理修复反馈', '2026-11-03')
    add('课程对象与权限', '实际运行结果', '登录、图谱与作答进入同一数据库', '登录 200\n2门课程 / 初期8个知识节点\n作答 201\n学习概览 200\n\n知识点种子占位符 8 → 7\n课程、章节与资源共享标识', '004记录中“实际结果”原文对应结果；当前课程已扩充', '2026-11-03', True)
    add('课程对象与权限', '中文提交', '保留架构演进', git('show', '-s', '--format=%h%n%s', 'e040be6') + '\n' + git('show', '-s', '--format=%h%n%s', '9b40105'), 'Git原始提交对象；同源契约与课程授权代码', '2026-11-03', True)

    prompt6 = (ROOT / 'XueMai_Codex_Upgrade_Round6.txt').read_text('utf8')
    relevant = [line for line in prompt6.splitlines() if '流程图' in line or '知识网络' in line]
    add('知识网络遮挡', '原始需求', '从拥挤流程图转向课程网络', '\n'.join(relevant)[:650], '第六轮任务书原文节选', '2026-11-12')
    add('知识网络遮挡', '实际几何检查', '节点已分开，连线仍有遮挡', '\n'.join(f"{row['nodes']}节点 / {row['edges']}关系　遮挡 {row['obstructions']}" for row in old_graph) + '\n\n输入与旧结果保留在对应Git版本。', '第六轮实际课程初次几何日志 / CS201遮挡9处', '2026-11-12', True)
    diff = git('show', 'a3b89fe', '--', 'frontend/src/graph-layout.ts')
    begin = diff.find('+function gridRoute')
    if begin < 0: begin = diff.find('@@')
    add('知识网络遮挡', '代码差异', '受阻时搜索空白通道', diff[begin:begin+1500], 'a3b89fe / graph-layout.ts实际差异节选', '2026-11-12', True)
    add('知识网络遮挡', '验证输入', '两门真实课程与不同规模网络', '\n'.join(f"{row.get('course','网络')}　{row['nodes']}节点 / {row['edges']}关系" for row in new_graph) + '\n\n节点碰撞、曲线遮挡、重排稳定、相机锚点分别校验。', '知识网络固定样例与实际几何结果', '2026-11-12', True)
    add('知识网络遮挡', '改进结果', '全部案例连线遮挡为零', '\n'.join(f"{row.get('course','网络')}　碰撞 {row['collisions']} / 遮挡 {row['obstructions']}" for row in new_graph), '第六轮知识网络几何验证.json / 已执行结果', '2026-11-12', True)
    add('知识网络遮挡', '中文提交', '布局与固定输入一起保存', git('show', '-s', '--format=%h%n%s', 'a3b89fe') + '\n\n浏览器继续验证搜索、拖动、适配全图与全屏恢复。', 'a3b89fe / 代码、样例、验证结果同次提交', '2026-11-12', True)

    add('教师混合意图', '本次原始任务', '核查教师助手是否完成教学要求', '新增DIA-TEACH专项验证。\n\n核对任务路由、专题证据、时间预算、群组题目、编辑保存与任务发布。\n\n实际请求\n“请基于这个班栈与队列的错误，设计一节30分钟讲评课。”', '第七轮任务书要求摘要与test_round7_workflow.py实际输入', '2026-11-12')
    initial = log('round7-teacher-initial.txt')
    add('教师混合意图', '实际失败', '设计请求落入学情分析', initial[max(0, initial.find('E       ')-600):][-2000:], '初次专项测试原始日志 / 1失败、1通过', '2026-11-12', True)
    add('教师混合意图', '定位与差异', '先识别教师要求的教学产物', git('show', '85d731e', '--', 'backend/app/teacher_assistant.py').split('@@', 2)[-1][:1700], '85d731e / teacher_assistant.py实际差异', '2026-11-12', True)
    add('教师混合意图', '专项复核', '讲评课草稿与轻量讨论均通过', log('round7-teacher-recheck.txt')[-1200:], '修复后同一专项测试输出', '2026-11-12', True)
    add('教师混合意图', '完整回归', '验证既有业务与两端页面', log('round7-backend.txt')[-650:] + '\n\n' + log('round7-e2e.txt')[-650:], '完整业务回归124项 / 浏览器31项', '2026-11-12', True)
    add('教师混合意图', '提交与真实演示', '方案进入同一教学任务', git('show', '-s', '--format=%h%n%s', '85d731e') + '\n\n真实Flash生成30分钟方案\n教师编辑保存并发布\n同一学生完成复测\n教师查看完成结果并反馈', '85d731e / 第七轮官方AI记录与教学闭环结果', '2026-11-12', True)

    boards = [dict(chain='学脉 XueMai', stage='教学场景', title='一道错题之后，怎样继续教与学',
                   text='陈星河把入栈顺序当成出栈顺序。\n\n从实际作答出发，连接学习路径、交互实验、个人辅导和教师的后续安排。', source='当前系统真实操作 / 数据结构课程为教学示例', date='师生双端AI个性化智慧教育平台', duration=20)]
    boards += [dict(chain='五项核心方法', stage='方法分工', title='共享学习证据，分别承担教学判断',
                    text='K-TRACE　独立性、相关性与时间修正\nPATH-G　先修约束与个人时间预算\nDIA-GUIDE　个人诊断、动作与理解检查\nCLASS-LOOP　错因群组与匹配题目\nDIA-TEACH　教师目标、班级证据与方案',source='课程、题目、学生和任务使用统一标识',date='规则计算与一次模型生成协作',duration=17.5),
               dict(chain='方法实验',stage='实际对照',title='约束满足与教学动作逐项验证',
                    text='PATH-G 对可行贪心　36胜 / 9平 / 3负\n平均目标值提升3.49%，先修与预算违规0\n\nCLASS-LOOP　缺失维度与0.06噪声检查\nDIA-TEACH　10项教学工具与流程验证通过',source='种子7011 / 原始输入与逐例结果随源码提供',date='合成案例的机制对照',duration=17.5)]
    boards += stages
    boards += [dict(chain='运行与复现',stage='工程交付',title='从统一入口进入完整系统',text='双击“启动学脉”\n\n两门课程正常初始化\n前后端源码、可编辑报告与视频源\n124项后端回归 / 31项浏览器回归\n478张完整界面截图',source='GitHub / Sunny1004-7 / xuemai-ai-platform',date='课程示例可扩充至不同学段与学科',duration=25),
               dict(chain='学脉 XueMai',stage='完整教学闭环',title='让下一步学习与教学安排相互连接',text='学生留下证据，系统提供行动。\n教师作出判断，结果继续回到课堂。',source='真实业务记录、方法实验与源代码共同呈现',date='师生双端AI个性化智慧教育平台',duration=10)]
    (OUT / 'boards.json').write_text(json.dumps(boards, ensure_ascii=False, indent=2), encoding='utf8')
    (ROOT / 'docs/development-process/008-第七轮三条开发证据链.json').write_text(json.dumps(stages, ensure_ascii=False, indent=2), encoding='utf8')
    print(len(stages), 'stages /', sum(x['duration'] for x in stages), 'seconds')


if __name__ == '__main__':
    build()
