"""生成本次演示的彩色开场、方法总图和真实开发记录回放页面。"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, str(ROOT/'scripts/build_demo_evidence.py')], check=True)
original = (ROOT/'docs/development-process/round2-replay.html').read_text('utf-8')
original = original.replace('</html>', '')
style = """
<style>
body{background:#f1f0e8;color:#263a37}section{position:relative;padding:64px 98px 88px}
section:after{content:"学脉 XueMai  /  课程知识 · 学习证据 · 教学行动";position:absolute;bottom:68px;left:100px;right:100px;border-top:1px solid #b8c8c0;padding-top:18px;font-size:18px;letter-spacing:2px;color:#52665f}
.quotes{gap:24px;grid-template-columns:1.08fr 1fr}.quotes article{border:1px solid #c3d2c9;border-top:5px solid #5e8c87;border-radius:4px;padding:25px 30px}.quotes article:nth-child(2){background:#e7edf0;border-color:#607e95}.quotes article:nth-child(3){background:#eee4d6;border-color:#a78a73}
.quotes p{font-size:21px;line-height:1.6}
footer{font-size:19px;margin-top:20px}.hero{display:grid;grid-template-columns:1fr 1fr;gap:70px;padding-top:55px}.hero h1{font:94px SimSun;margin:50px 0 25px}.hero .subtitle{font-size:31px;line-height:1.9}.stamp{display:inline-block;background:#2e6a67;color:white;padding:10px 18px;font-size:20px;letter-spacing:3px}.hero-figure{background:#fdfcf8;border:1px solid #a9c8be;padding:35px;border-radius:50% 50% 4px 4px;height:650px}.hero-note{font-size:21px;line-height:1.9;color:#52665f;margin-top:58px}
.method-grid{display:grid;grid-template-columns:1fr 1fr;gap:25px;margin-top:32px}.method-grid .method{grid-row:auto;padding:28px 34px;border-left:6px solid #2e6a67;background:#e0ece5;min-height:210px}.method:nth-child(2){border-color:#607e95;background:#e5ebef}.method:nth-child(3){border-color:#a78a73;background:#eee4d7}.method:nth-child(4){border-color:#6c7f4f;background:#e7ebdf}.method b{font:36px "Times New Roman";letter-spacing:1px}.method h3{font-size:25px;margin:14px 0}.method p{font-size:22px;line-height:1.7}.evidence-line{display:flex;gap:15px;flex-wrap:wrap;margin-top:25px}.evidence-line span{background:#fdfcf8;border:1px solid #b8c8c0;padding:10px 18px;font-size:20px}
.closing{padding-top:130px}.closing h1{font:76px/1.65 SimSun}.closing .pill{display:inline-block;border-bottom:4px solid #c6a348;padding-bottom:16px;font-size:28px}
</style>
"""
intro = """
<section id="intro"><span class="stamp">智慧教育 · 师生协同</span><div class="hero"><div><h1>学脉 XueMai</h1><p class="subtitle">从一次作答，走向下一步学习<br>让教师看见差异，让学生获得回应</p><div class="evidence-line"><span>31个知识点</span><span>28人教学班</span><span>四项教学方法</span></div><p class="hero-note">本机系统操作与已发生开发记录回放<br>合成教学样本 · 本地示例辅导 · 中文合成配音</p></div><div class="hero-figure"><svg viewBox="0 0 720 610" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><defs><marker id="tip" orient="auto" markerWidth="8" markerHeight="8" refX="7" refY="4"><path d="M0 0L8 4L0 8Z" fill="#5e8c87"/></marker></defs><g fill="none" stroke="#a9c8be" stroke-width="3" marker-end="url(#tip)"><path d="M360 110V185M360 270L180 330M360 270L540 330M180 410L360 475M540 410L360 475"/></g><g text-anchor="middle" font-family="Microsoft YaHei" font-size="25" fill="#263a37"><rect x="230" y="35" width="260" height="80" rx="40" fill="#d7e6db"/><text x="360" y="84">课程知识</text><circle cx="360" cy="225" r="68" fill="#2e6a67"/><text x="360" y="219" fill="white">学习</text><text x="360" y="252" fill="white">证据</text><rect x="60" y="330" width="240" height="80" rx="15" fill="#e5ebef"/><text x="180" y="379">个性化路径</text><rect x="420" y="330" width="240" height="80" rx="15" fill="#eee4d7"/><text x="540" y="379">协作式辅导</text><rect x="230" y="478" width="260" height="80" rx="40" fill="#e7ebdf"/><text x="360" y="527">教师教学行动</text></g></svg></div></div></section>
"""
methods = """
<section id="round3"><small>2026年11月10日 · 实际实现、中文阶段提交与自动化反馈</small><h1>从证据出发，组织可执行的教学</h1><div class="method-grid"><article class="method"><b>K-TRACE</b><h3>相关性修正的多维知识证据追踪</h3><p>提示、部分得分、时间与相近题相关性共同决定更新。<br>42a3a64 · 知识证据相关性折减与路径搜索</p></article><article class="method"><b>PATH-G</b><h3>先修约束的多目标学习路径规划</h3><p>有限束搜索同时满足先修顺序与当次时间预算。<br>24组合成案例：先修与预算违规均为0</p></article><article class="method"><b>DIA-GUIDE</b><h3>诊断—干预—校验协作教学编排</h3><p>规则诊断与校验连接一次模型生成；理解反馈驱动下轮策略。<br>4588983 · 接通协作辅导并启用正式服务</p></article><article class="method"><b>CLASS-LOOP</b><h3>基于错因距离的动态教学分层</h3><p>按六维错因特征聚类，匹配已审核题目并发布任务。<br>e21481c · 扩充二十八人教学样本与动态分组</p></article></div><div class="evidence-line"><span>97项后端功能与方法检查通过</span><span>14项浏览器流程通过</span><span>4次官方接口抽样成功</span></div><footer>上述数据对应程序化机制案例和实际回归；四次联调分别覆盖辅导、出题、备课与量规评阅。<br>常规验证、截图和本次录制均使用Mock；原始开发消息回放保留来源日期。</footer></section>
<section id="outro" class="closing"><span class="stamp">学脉 XueMai</span><h1>让学习建议能够执行<br>让教学安排有据可循</h1><p class="pill">知识结构　·　学习证据　·　教学行动</p><p style="font-size:24px;margin-top:65px">github.com/Sunny1004-7/xuemai-ai-platform</p></section>
"""
(ROOT/'docs/development-process/round3-replay.html').write_text(original+style+intro+methods+'</html>', 'utf-8')
print('已生成彩色开场、四项方法与三组原始记录回放')
