"""按真实连续素材建立第八轮剪辑和语段时间轴，不生成模型请求。"""
import json
from pathlib import Path
import shutil
import subprocess

import av
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/demo/第八轮演示源'
LOCAL = ROOT / '.local/round8-edit'
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def build():
    LOCAL.mkdir(exist_ok=True, parents=True)
    media = OUT / 'media'
    media.mkdir(exist_ok=True)
    for name in ['tour', 'boards', 'boards-patch']:
        source = ROOT / '.local/round8-tour'
        if name.startswith('boards'):
            pointer = ROOT / '.local' / ('round8-' + name + '-current.json')
            if not pointer.exists():
                if (media / (name + '-continuous.mp4')).exists():
                    continue
                raise FileNotFoundError('缺少已交付的连续录屏素材：' + name)
            source = Path(json.loads(pointer.read_text('utf8'))['directory'])
        for filename in ['continuous.mp4', 'continuous.webm', 'recording.json', 'timeline.json', 'events.json']:
            path = source / filename
            if path.exists():
                shutil.copy2(path, media / (name + '-' + filename))
    old = ROOT / 'docs/demo/第七轮演示源/media'
    sources = {name: old / (name + '-continuous.mp4') for name in ['system', 'student-review', 'review', 'follow']}
    sources |= {name: media / (name + '-continuous.mp4') for name in ['tour', 'boards', 'boards-patch']}
    boards = json.loads((media / 'boards-timeline.json').read_text('utf8'))
    recording = json.loads((media / 'boards-recording.json').read_text('utf8'))
    boards_origin = recording['elapsed_seconds'] - boards[-1]['at'] - boards[-1]['duration']
    patch = json.loads((media / 'boards-patch-timeline.json').read_text('utf8'))
    patch_recording = json.loads((media / 'boards-patch-recording.json').read_text('utf8'))
    patch_origin = patch_recording['elapsed_seconds'] - patch[-1]['at'] - patch[-1]['duration']
    tour = {row['name']: row['at'] + .31 for row in json.loads((media / 'tour-timeline.json').read_text('utf8'))}
    scenes, edits = [], []
    cursor = 0

    def clip(source, begin, end, category):
        nonlocal cursor
        frames = round((end - begin) * 30)
        duration = frames / 30
        index = len(edits)
        target = LOCAL / f'clip-{index:02}.mp4'
        subprocess.run([FFMPEG, '-y', '-v', 'error', '-ss', str(begin), '-i', str(sources[source]),
                        '-an', '-frames:v', str(frames), '-r', '30', '-c:v', 'libx264', '-preset', 'veryfast',
                        '-crf', '19', '-pix_fmt', 'yuv420p', str(target)], check=True)
        start = cursor
        edits.append({'source': sources[source].relative_to(ROOT).as_posix(), 'in': begin, 'out': end,
                      'start': start, 'duration': duration, 'frames': frames, 'category': category})
        cursor += duration
        return start, duration

    def say(start, duration, name, text):
        scenes.append({'id': f'r8-{len(scenes)+1:02}', 'name': name, 'start': round(start, 3),
                       'duration': round(duration, 3), 'text': text})

    def board(name, duration):
        amended = isinstance(name, int) or name == 'framework'
        row = next(row for row in (patch if amended else boards) if row['name'] == name)
        origin = patch_origin if amended else boards_origin
        return clip('boards-patch' if amended else 'boards', row['at'] + origin, row['at'] + origin + duration, '开发过程' if isinstance(name, int) else '作品说明')

    author = json.loads((ROOT / 'docs/submission-facts.json').read_text('utf8'))['author']
    start, duration = board('intro', 16)
    say(start, duration, '问候与介绍', f'各位评委老师好，我是{author["school"]}{author["major"]}专业的{author["name"]}。我的作品是学脉，一套面向课后巩固与分层指导的师生双端平台。')
    start, duration = board('pain', 22)
    say(start, duration, '真实教学痛点', '学生做错一道题，接下来该翻哪份讲义、看哪段视频，往往还要自己寻找。教师看到全班的错误，也要判断谁需要什么帮助。学脉从这些具体困难出发，把学习反馈接到可以继续完成的活动和教学任务上。')
    start, duration = board('framework', 27)
    say(start, duration, '总体方法框架', '这张图呈现学脉的总体方法。学生侧由知识追踪提供状态，路径规划安排先修和时间，个人辅导检验理解。教师侧根据错因形成群组，再编排教学方案。两端共享课程、资料和学习证据，结合模型生成、业务校验与教师审核，将新的作答和反馈持续写回。')
    start, duration = clip('tour', tour['登录诗句'], tour['学生回看辅导'], '系统界面')
    say(start, duration, '双角色入口', '师生各有工作区，课程与学习记录在两端保持关联。')
    student, _ = clip('system', .31, 59, '系统界面')
    say(student, 19.08, '从错题到学习路径', '从陈星河的一次错题开始。系统记录这次错误，呈现知识状态、证据量和继续学习的入口。路径读取个人目标和时间预算，安排具体的前置活动。')
    say(student + 19.08, 19.19, '知识网络与操作实验', '课程网络连接当前概念与前置知识，方便学生定位。压入四十八再弹出，结构和返回值同步变化。学生带上原题和操作记录，继续讨论自己的困惑。')
    say(student + 38.27, 20.42, '真实辅导与理解检查', '这次请求使用官方模型。解释结合课程材料与附件，并给出理解检查。打开引用，可以查看上传的丙牌操作记录。学生完成检查，评分结果保存到原有会话和学习记录。')
    start, duration = clip('student-review', .31, 18.5, '系统界面')
    say(start, duration, '学生辅导结果', '回看这段解释，模型用甲乙丙牌说明最后压入的元素为什么先离开。学生既能看到对应材料，也能通过下一道题检查自己的理解。辅导围绕这名学生的具体错误展开。')
    start, duration = clip('tour', tour['学生解释可读'], tour['学生接收教师反馈'], '系统界面')
    say(start, duration, '会话与证据延续', '历史会话保留原题、引用和检查。学生再次打开时，可以接着同一个问题学习。')
    teacher, _ = clip('system', 59, 89.46, '系统界面')
    say(teacher, 30.46, '教师分析与教学规划', '教师从知识矩阵进入陈星河的作答，把班级状态追溯到具体题目。随后要求安排三十分钟讲评课，教学助手读取班级证据，组织教学环节与群组任务。教师修改方案标题，核对活动安排，保存为可继续编辑的课程教案。方案经过校验，等待教师确认。')
    start, duration = clip('review', 21.1, 40.7, '系统界面')
    say(start, duration, '教师方案结果', '教师端面向整个班级。方案分为五分钟发现问题、十五分钟对照追踪和十分钟迁移复测。群组与题目来自课程工具，时间和对象由程序校验，教师据此判断哪些内容适合这次教学。')
    start, duration = clip('system', 89.46, 100.3, '系统界面')
    say(start, duration, '审核发布', '发布表单带入五名学生，其中包括陈星河。教师确认目标学生与题目，再发布独立复测任务。')
    follow, _ = clip('follow', 1.5, 32.2, '系统界面')
    say(follow, 30.7, '学生完成与教师反馈', '陈星河接收该任务，独立选择答案并提交，记录保留任务标识。教师查看同一任务的结果，确认他已经完成，并对照新增作答和发布前后的状态。随后继续发起反馈，请学生解释两种移出顺序，并举出生活中的例子。这几步通过同一课程、学生和任务相互关联，便于回看后续学习。')
    start, duration = clip('tour', tour['学生接收教师反馈'], tour['新增原创单元'], '系统界面')
    say(start, duration, '学生回应与教师回看', '学生回到课堂互动，写下对栈和队列的理解，再提交自己的例子。教师随后查看这条回答。一次错误经过材料、辅导、复测和反馈，形成了前后对应的教学过程。每一步都保存具体的课程对象与实际记录。')
    start, duration = clip('tour', tour['新增原创单元'], tour['Python课程学习'], '系统界面')
    say(start, duration, '正常接入新内容', '课程建设也可以接入新的主题。这里是通过正常接口创建的信息素养微单元，讲义讨论怎样追溯消息来源。学生进入新知识和习题，老师发布任务、查看结果并继续反馈，同一套流程沿用到新内容。')
    start, duration = clip('tour', tour['Python课程学习'], tour['补充演示结束'], '系统界面')
    say(start, duration, '另一门课程与方法验证', 'Python课程同样提供视频、知识关系和练习。方法效果则用可运行对照检查：四十八个相同约束案例中，路径搜索相对可行贪心取得三十六胜、九平、三负，平均目标值提高约百分之三点四九。每个案例及结果都随源码提供。')
    narration = [
        '接下来回看三条真实开发链，先看课程对象与权限的协作指令。',
        'Codex先固定接口契约，前后端与人工智能模块共用课程标识。',
        '联测发现初始化错误，三个路由测试被同一个数据问题阻断。',
        '反馈后，代码将知识点种子的八个占位符修正为七个。',
        '修复后的登录、图谱和作答返回实际结果，记录进入同一数据库。',
        '中文提交保留数据初始化和课程授权，后续功能沿用这些对象。师生页面由此能够继续使用同一份课程记录。',
        '第二条来自知识网络。原始要求是改善拥挤的布局与阅读体验。',
        '实际几何检查发现九处连线遮挡，问题被保留在验证记录里。',
        'Codex增加空白通道搜索，使受阻连线继续寻找可用路径。',
        '两门真实课程和不同规模网络使用固定输入，分别检查几何结果。',
        '改进后，全部案例的节点碰撞与连线遮挡均为零。',
        '代码、固定输入和结果一起提交，再检查页面中的相机与全屏。相同输入可以再次执行，逐项核对。',
        '第三条核查教师要求，一句指令同时包含班级错误与教学设计。',
        '专项测试真实失败，系统只返回学情分析，遗漏讲评课产物。',
        'Codex调整优先级，先识别教学产物，再使用班级错误作为证据。',
        '同一专项重新执行，两项通过，教学设计与轻量讨论分别核查。',
        '随后验证既有业务和双端页面，回归结果保留当时的执行记录。',
        '中文提交保存修复，真实教学方案继续进入任务发布和学生反馈。',
    ]
    development_start = cursor
    for index in range(len(narration)):
        board(index, 7.5)
    for chain in range(3):
        say(development_start + chain * 45, 45, '真实开发链' + str(chain + 1), ''.join(narration[chain*6:chain*6+6]))
    start, duration = board('outro', 14)
    say(start, duration, '总结与感谢', '学脉希望让学生的下一步学习有据可循，让教师接得住每一次反馈。我的介绍到这里，感谢各位评委老师观看。')
    concat = LOCAL / 'concat.txt'
    concat.write_text('\n'.join(f"file '{(LOCAL / f'clip-{i:02}.mp4').as_posix()}'" for i in range(len(edits))), 'utf8')
    target = ROOT / '最终参赛提交材料/学脉XueMai-演示视频.mp4'
    subprocess.run([FFMPEG, '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(concat),
                    '-c', 'copy', '-movflags', '+faststart', str(target)], check=True)
    with av.open(str(target)) as container:
        actual = container.duration / av.time_base
    timeline = {'duration_seconds': actual, 'fps': 30, 'development_evidence_seconds': cursor - duration - development_start,
                'system_interface_seconds': sum(e['duration'] for e in edits if e['category'] == '系统界面'),
                'real_api_calls_new': 0, 'reused_round7_real_calls': 2, 'edits': edits}
    if not 300 <= actual <= 480:
        raise ValueError('片长超出官方要求')
    (OUT / 'edit-timeline.json').write_text(json.dumps(timeline, ensure_ascii=False, indent=2), 'utf8')
    (OUT / 'scenes.json').write_text(json.dumps(scenes, ensure_ascii=False, indent=2), 'utf8')
    print(json.dumps({key: value for key, value in timeline.items() if key != 'edits'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    build()
