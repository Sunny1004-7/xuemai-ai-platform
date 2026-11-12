"""先按实际连续录屏建立剪辑，再生成与画面对应的逐句解说时间轴。"""
import json
from pathlib import Path
import shutil
import subprocess

import av
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/demo/第七轮演示源'
LOCAL = ROOT / '.local/round7-edit'
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def build():
    LOCAL.mkdir(exist_ok=True, parents=True)
    media = OUT / 'media'
    media.mkdir(exist_ok=True)
    sources = {
        'system': ROOT / '.local/round7-loop/2026-11-12T07-17-05-022Z',
        'follow': ROOT / '.local/round7-loop/2026-11-12T07-20-30-879Z',
        'review': ROOT / '.local/round7-response-review',
        'student-review': ROOT / '.local/round7-student-review',
        'board': ROOT / '.local/round7-evidence-video',
        'method': ROOT / '.local/round7-method-board',
    }
    for name, directory in sources.items():
        for filename in ['continuous.mp4', 'recording.json', 'events.json', 'timeline.json']:
            if (directory / filename).exists():
                shutil.copy2(directory / filename, media / f'{name}-{filename}')
    board = json.loads((media / 'board-timeline.json').read_text('utf8'))
    edits, scenes = [], []
    cursor = 0

    def clip(name, start, end):
        nonlocal cursor
        # 最终片长按30fps的整帧边界组织。
        frames = round((end - start) * 30)
        duration = frames / 30
        index = len(edits)
        target = LOCAL / f'clip-{index:02}.mp4'
        command = [FFMPEG, '-y', '-v', 'error', '-ss', str(start), '-i', str(media / f'{name}-continuous.mp4'),
                   '-an', '-frames:v', str(frames), '-r', '30', '-c:v', 'libx264', '-preset', 'veryfast',
                   '-crf', '19', '-pix_fmt', 'yuv420p', str(target)]
        subprocess.run(command, check=True)
        edits.append({'source': name, 'in': start, 'out': end, 'start': cursor, 'duration': duration, 'frames': frames})
        begin = cursor
        cursor += duration
        return begin, duration

    def say(start, duration, name, text):
        scenes.append(dict(id=f'r7-{len(scenes)+1:02}', name=name, start=round(start,3), duration=round(duration,3), text=text))

    # 共享提示条出现前后的原生流导出均保留完整应用外壳，录屏启动前导约0.3秒。
    board_origin = .31
    def board_at(index):
        return board[index]['at'] + board_origin

    start, duration = clip('board', board_at(0), board_at(1))
    say(start, duration, '一道错题的后续', '学生做错一道题之后，怎样继续学，教师又怎样接住这条反馈？学脉把学习证据、个人辅导和教学安排放进同一个过程。这里以陈星河的栈与队列学习为例。')
    student_start, _ = clip('system', .31, 59.0)
    marks = [
        (0, 5, '首次作答', '陈星河选了一，提交这次答案。'),
        (5, 12.3, '证据反馈', '错误反馈关联到具体知识，提示使用与近期作答共同影响本次证据权重。'),
        (12.3, 19.1, '预算内路径', '学习路径读取个人目标和时间预算，先安排可执行的前置活动。'),
        (19.1, 25.7, '知识网络', '课程网络呈现知识依赖，学生可以定位当前概念并继续探索。'),
        (25.7, 32.25, '交互实验', '压入再弹出四十八，结构和返回值同步变化。'),
        (32.25, 38.3, '题目与附件', '携带原题和操作记录，让辅导回应具体困惑。'),
        (41.3, 46.3, '学生真实AI', '官方模型返回课程内的辅导和理解检查。'),
        (46.3, 52, '附件引用', '点击引用，能够回看本次上传的丙牌操作记录。'),
        (52, 58.69, '理解检查', '学生完成理解检查，实际评分和反馈保存到同一会话。'),
    ]
    for begin, end, name, text in marks:
        say(student_start + begin, end - begin, name, text)
    start, duration = clip('student-review', .31, 18.5)
    say(start, duration, '回看个人解释', '再回看这次真实解释。模型用甲乙丙牌说明最后压入的元素位于栈顶，引用直接指向上传记录。个人辅导围绕这名学生的错误组织反例，并通过课程题检验理解。')
    teacher_start, _ = clip('system', 59.0, 89.46)
    teacher_marks = [
        (0, 9.3, '教师证据下钻', '教师查看陈星河在栈与队列上的原始作答，把班级矩阵中的状态追溯到具体证据。'),
        (9.3, 15.4, '教师教学目标', '依据班级错误，安排三十分钟讲评和练习。'),
        (15.4, 21.4, '教师真实AI', '助手读取班级证据，生成教学环节和群组任务。'),
        (21.4, 30.46, '教师编辑保存', '教师修改教案标题，确认活动安排，再保存为课程教案草稿。'),
    ]
    for begin, end, name, text in teacher_marks:
        say(teacher_start+begin, end-begin, name, text)
    start, duration = clip('review', 21.1, 40.7)
    say(start, duration, '回看教学方案', '教师端面向整个班级组织教学。方案把时间分为五分钟发现问题、十五分钟对照追踪和十分钟迁移复测。群组与题目来自课程工具，生成内容经过时间和对象校验，再交由教师审核。')
    start, duration = clip('system', 89.46, 100.3)
    say(start, duration, '审核与发布', '审核表单带入迁移应用关注组的五名学生，其中包括陈星河。教师确认一道多选题后，发布独立复测任务。')
    follow_start, _ = clip('follow', 1.5, 32.2)
    for begin, end, name, text in [
        (0,8.5,'学生完成任务','陈星河接收同一任务，独立选择答案并提交，作答保留任务标识。'),
        (8.5,20.1,'教师查看新增结果','教师回到该任务查看结果，陈星河已经完成，页面同时呈现新增有效证据和发布前后的状态。'),
        (20.1,30.7,'教师形成反馈','教师继续发布复测反馈，请学生解释两种移出顺序，并举出生活例子。学习结果由此回到下一次课堂交流。'),
    ]:
        say(follow_start+begin,end-begin,name,text)
    method_start, _ = clip('method', .31, .31 + board_at(3) - board_at(1))
    say(method_start,board[1]['duration'],'五项方法的分工','五项方法共享课程对象和学习证据。知识追踪估计个人状态，路径规划安排先后顺序，错因分层形成教学关注。学生辅导检验个人理解，教师编排组织全班的后续行动。')
    say(method_start+board[1]['duration'],board[2]['duration'],'实验对照','相同约束下，路径搜索对可行贪心取得三十六胜、九平、三负，平均目标值提高约百分之三点四九。原始结果保留全部案例，另有分层扰动和教师流程专项验证。')
    dev_start, _ = clip('board', board_at(3), board_at(21))
    narration = [
        '接下来回放三条真实开发链。第一条来自十一月三日的课程与权限实现。',
        'Codex先固定接口契约，使前端、后端和人工智能模块共享课程标识。',
        '联测发现种子初始化阻断了三个路由测试，问题被直接反馈给后端。',
        '后端定位字段数量与占位符不一致，将八个占位符修正为七个。',
        '修复后，登录、图谱和作答得到实际响应，课程对象进入同一数据库。',
        '两次中文提交保存数据初始化与课程授权，后续实现继续沿用这些对象。',
        '第二条是课程知识网络。原始要求是重做拥挤的流程图式布局。',
        '实际课程的几何检查仍发现九处遮挡，节点分开后还需要处理连线。',
        '代码增加空白通道搜索，曲线候选受阻时沿可用区域寻找路径。',
        '固定输入覆盖两门课程及不同规模网络，并分别检查碰撞和相机。',
        '改进后，各个案例的节点碰撞和连线遮挡都为零。',
        '对应提交同时保存算法、固定输入和验证结果，页面再检查全屏恢复。',
        '第三条来自本次教师专项，一句请求同时包含班级错误和教学设计。',
        '新增测试真实失败。系统返回学情分析，遗漏了要求的讲评课产物。',
        'Codex据此调整优先级，先识别教学产物，再使用班级错误作为证据。',
        '同一专项重新执行，两项通过，教学设计与轻量讨论均得到检查。',
        '完整业务回归一百二十四项通过，浏览器师生流程三十一项通过。',
        '中文提交保存修复，真实方案进入任务发布和反馈。',
    ]
    for index,text in enumerate(narration):
        say(dev_start+board[index+3]['at']-board[3]['at'],7.5,'真实开发证据'+str(index+1),text)
    start,duration=clip('board',board_at(21),board_at(22))
    say(start,duration,'运行与复现','从统一启动入口可以进入完整系统。两门课程通过正常初始化导入，源码、可编辑技术文档、视频工程、实验原始结果和完整界面截图共同交付。常规回归使用本地示例，少量官方请求保留实际用量和教学结果。')
    start,duration=clip('board',board_at(22),board_at(22)+10)
    say(start,duration,'结尾','学生留下证据，系统提供行动，教师作出判断。学脉让下一步学习与教学安排持续连接。')
    concat=LOCAL/'concat.txt'
    concat.write_text('\n'.join(f"file '{(LOCAL/f'clip-{i:02}.mp4').as_posix()}'" for i in range(len(edits))),encoding='utf8')
    target=ROOT/'最终参赛提交材料/学脉XueMai-演示视频.mp4'
    subprocess.run([FFMPEG,'-y','-v','error','-f','concat','-safe','0','-i',str(concat),'-c','copy','-movflags','+faststart',str(target)],check=True)
    with av.open(str(target)) as container:
        actual=float(container.duration)/av.time_base
    timeline={'duration_seconds':actual,'fps':30,'development_evidence_seconds':edits[-3]['duration'],'edits':edits,'real_model_calls':2,'automatic_retries':0}
    (OUT/'edit-timeline.json').write_text(json.dumps(timeline,ensure_ascii=False,indent=2),encoding='utf8')
    (ROOT/'scripts/demo-scenes.json').write_text(json.dumps(scenes,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(timeline,ensure_ascii=False),flush=True)


if __name__=='__main__':
    build()
