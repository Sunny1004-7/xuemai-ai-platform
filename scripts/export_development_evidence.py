"""Export an allowlisted public development record from this project's sessions.

This is intentionally NOT a transcript dumper. Only visible user/assistant
messages, three collaboration operations and test command/exit-code pairs are
selected. All other records and all non-allowlisted fields are ignored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = {
    "root": "rollout-2026-11-03T14-37-42-01a1a020-bc08-7da2-9bac-6a75a1ee93c6.jsonl",
    "backend": "rollout-2026-11-03T14-39-18-01a1a022-3487-7d13-b5a2-42532d801d2e.jsonl",
    "frontend": "rollout-2026-11-03T14-39-31-01a1a022-6510-74b3-b83f-aa44139dca1d.jsonl",
    "ai": "rollout-2026-11-03T14-39-40-01a1a022-87d6-70f2-9065-a473638ccff7.jsonl",
}
APPENDIX = ROOT / "docs" / "development-process" / "004-核心功能实际协作逐字转存.md"
OPERATIONS = {"spawn_agent", "send_message", "followup_task"}
VISIBLE_PHASES = {"commentary": "commentary", "final": "final", "final_answer": "final"}
OPAQUE = re.compile(r"gAAAA[A-Za-z0-9_-]{30,}={0,2}")
FEATURES = {
    "graph": "知识图谱与资源联动",
    "practice": "练习、作业与学习推荐",
    "ai": "DeepSeek 辅导与检索",
}
FEATURE_WORDS = {
    "graph": re.compile(r"图谱|先修|章节|knowledge|graph|课程授权", re.I),
    "practice": re.compile(r"习题|题目|作业|错题|评分|复核|学情|推荐|practice|attempt|assignment|mistake|mastery|recommend", re.I),
    "ai": re.compile(r"DeepSeek|\bAI\b|SSE|检索|辅导|Token|FTS|ai[_. /]|预算|流式", re.I),
}
TEST_INVOCATION = re.compile(
    r"(?:pytest(?:\s|$)|python(?:\.exe)?[\"']?\s+-m\s+(?:pytest|compileall)|"
    r"(?:npm|npx)(?:\.cmd)?\s+(?:run\s+(?:build|test)|test|playwright\s+test)|"
    r"scripts[/\\]test\.ps1|scripts[/\\](?:scan_secrets|secret_scan|check_secrets)\.py)", re.I,
)
SECRET_PATTERNS = [
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "[已移除 API 密钥]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{12,}\b"), "[已移除访问令牌]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{12,}\b"), "[已移除访问令牌]"),
    (re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9_.~+/-]{16,}"), r"\1[已移除会话令牌]"),
    (re.compile(r"(?i)(?:DEEPSEEK_API_KEY\s*=\s*)[^\s\"'`;,]{8,}"), 'DEEPSEEK_API_KEY="[已移除密钥值]"'),
    (re.compile(r"(?i)(?:授权码|设备码|一次性(?:认证|验证)?码|user[_ -]?code|device[_ -]?code)\s*[:：=]?\s*[A-Z0-9]{4}[- ]?[A-Z0-9]{4}\b"), "[已移除一次性认证码]"),
    (re.compile(r"\b[A-Z]{4}-[A-Z]{4}\b"), "[已移除一次性认证码]"),
]


class Sanitizer:
    def __init__(self):
        self.counts = Counter()
        self.replacements = [(str(ROOT), "[项目目录]"), (str(ROOT).replace("\\", "/"), "[项目目录]")]
        profile = os.getenv("USERPROFILE")
        if profile:
            self.replacements.extend([(profile, "[用户目录]"), (profile.replace("\\", "/"), "[用户目录]")])

    def text(self, value: str) -> str:
        value, count = OPAQUE.subn("[加密内容未导出]", value)
        self.counts["opaque_content_omitted"] += count
        for pattern, replacement in SECRET_PATTERNS:
            value, count = pattern.subn(replacement, value)
            self.counts["credential_or_auth_code"] += count
        for original, replacement in self.replacements:
            value, count = re.subn(re.escape(original), replacement, value, flags=re.I)
            self.counts["personal_or_project_absolute_path"] += count
        # Drop remaining user/home locations while preserving relative filenames.
        value, count = re.subn(r"(?i)[A-Z]:[/\\]Users[/\\][^\r\n\"'<>`;,]*", "[用户目录]", value)
        self.counts["personal_or_project_absolute_path"] += count
        value, count = re.subn(r"(?<![\w:])/(?:Users|home)/[^\r\n\"'<>`;,]*", "[用户目录]", value)
        self.counts["personal_or_project_absolute_path"] += count
        # Account emails can occur in visible environment checks.
        value, count = re.subn(r"\b[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[已移除个人邮箱]", value)
        self.counts["personal_email"] += count
        return value

    def value(self, value):
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, dict):
            return {key: self.value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.value(item) for item in value]
        return value


def visible_text(payload: dict) -> str:
    parts = []
    for block in payload.get("content", []):
        if isinstance(block, dict) and block.get("type") in {"input_text", "output_text"}:
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts)


def test_commands(command) -> list[str]:
    if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
        return []
    # CommandExecution stores executable/flags/body in a list. Examine only the
    # command body, never output, cwd or environment snapshots.
    body = command[-1] if command else ""
    if not any(flag.lower() in {"-command", "-c", "/c"} for flag in command[:-1]):
        body = " ".join(command)
    return [segment.strip() for segment in re.split(r"[;\r\n]+", body)
            if segment.strip() and TEST_INVOCATION.search(segment)]


def feature_tags(record: dict) -> list[str]:
    text = record.get("text", "") + " " + json.dumps(record.get("arguments", {}), ensure_ascii=False) + " " + record.get("command", "")
    tags = [name for name, expression in FEATURE_WORDS.items() if expression.search(text)]
    if record.get("kind") == "user_message":
        return list(FEATURES)
    if not tags:
        tags = {"backend": ["graph", "practice"], "frontend": list(FEATURES), "ai": ["ai"], "root": list(FEATURES)}[record["source"]]
    return tags


def select_public(record: dict, source: str, line_number: int, call_ids: dict) -> list[dict]:
    """Access ONLY whitelisted record types, then ONLY whitelisted fields."""
    kind = record.get("type")
    if kind not in {"response_item", "event_msg"}:
        return []
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return []
    subtype = payload.get("type")
    base = {"source": source, "source_line": line_number, "timestamp": record.get("timestamp")}
    if kind == "response_item" and subtype == "message":
        role = payload.get("role")
        phase = payload.get("phase", payload.get("channel"))
        if role == "user":
            text = visible_text(payload)
            # Host context is not an instruction typed by the user.
            if text.lstrip().startswith(("<environment_context>", "<external_codex_apps_open_page>")):
                return []
            origin = "user_ui_reply" if text.lstrip().startswith("<send_user_message_question_reply>") else "user_original"
            return [{**base, "kind": "user_message", "role": "user", "origin": origin, "text": text}] if text else []
        if role == "assistant" and phase in VISIBLE_PHASES:
            text = visible_text(payload)
            return [{**base, "kind": "assistant_message", "role": "assistant", "channel": VISIBLE_PHASES[phase], "text": text}] if text else []
        return []
    if kind == "response_item" and subtype == "function_call":
        if payload.get("namespace") != "collaboration" or payload.get("name") not in OPERATIONS:
            return []
        arguments = payload.get("arguments")
        try:
            arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
        except ValueError:
            return []
        if not isinstance(arguments, dict):
            return []
        selected = {key: arguments[key] for key in ("message", "target", "task_name") if key in arguments}
        call_id = payload.get("call_id")
        call_ids[call_id] = payload["name"]
        message = selected.get("message")
        if isinstance(message, str) and OPAQUE.fullmatch(message):
            selected.pop("message")
            return [{**base, "kind": "ai_collaboration_metadata", "operation": payload["name"], "call_id": call_id,
                     "arguments": selected, "content_available": False,
                     "notice": "协作发生的时间和接收任务可核验；原始参数正文在会话存储中加密，本导出不读取或解密该内容，不能将本条当作完整 Prompt。"}]
        return [{**base, "kind": "ai_collaboration_prompt", "operation": payload["name"], "call_id": call_id, "arguments": selected}]
    if kind == "response_item" and subtype == "function_call_output":
        call_id = payload.get("call_id")
        if call_id not in call_ids:
            return []
        output = payload.get("output")
        try:
            decoded = json.loads(output) if isinstance(output, str) else output
        except ValueError:
            decoded = output
        # The three operations return a task name, short acknowledgement or null.
        if isinstance(decoded, dict):
            decoded = {key: decoded[key] for key in ("task_name", "status", "message", "error") if key in decoded}
        elif not isinstance(decoded, (str, type(None))):
            decoded = "[仅保留协作回执类型]"
        if decoded in (None, "", {}) or isinstance(decoded, str) and OPAQUE.fullmatch(decoded):
            return []
        return [{**base, "kind": "ai_collaboration_result", "operation": call_ids[call_id], "call_id": call_id, "result": decoded}]
    if kind == "response_item" and subtype == "agent_message":
        # Explicitly approved public delivery envelope: input_text only. The
        # separate encrypted block is never accessed. Most envelopes have an
        # empty Payload; those are not exported as if they contained a prompt.
        text = visible_text(payload)
        body = text.split("Payload:", 1)[1].strip() if "Payload:" in text else ""
        if not body or OPAQUE.fullmatch(body):
            return []
        return [{**base, "kind": "ai_collaboration_received", "text": text}]
    if kind == "event_msg" and subtype == "item_completed":
        item = payload.get("item")
        if not isinstance(item, dict) or item.get("type") != "CommandExecution":
            return []
        return [{**base, "kind": "test_command", "command": command, "exitCode": item.get("exit_code")}
                for command in test_commands(item.get("command"))]
    return []


def audit(value):
    serialized = json.dumps(value, ensure_ascii=False)
    if OPAQUE.search(serialized):
        raise ValueError("安全扫描阻止导出：检测到不应保留的加密串")
    for pattern, _ in SECRET_PATTERNS:
        if pattern.search(serialized):
            raise ValueError("安全扫描阻止导出：检测到未脱敏凭据或认证码")
    if re.search(r"(?i)[A-Z]:[/\\]+Users[/\\]+|/(?:Users|home)/", serialized):
        raise ValueError("安全扫描阻止导出：检测到个人绝对路径")
    forbidden_keys = {"analysis", "reasoning", "encrypted_content", "raw_content", "summary_text", "base_instructions", "aggregated_output", "cwd", "developer", "system"}
    def inspect(item):
        if isinstance(item, dict):
            if forbidden_keys.intersection(item):
                raise ValueError("安全扫描阻止导出：检测到不允许的字段")
            for child in item.values():
                inspect(child)
        elif isinstance(item, list):
            for child in item:
                inspect(child)
    inspect(value)


def build_html(bundle: dict) -> str:
    data = json.dumps(bundle, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>学脉 · 原始开发证据回放</title>
<style>:root{font-family:"Microsoft YaHei","PingFang SC",sans-serif;color:#17233b;background:#f4f7fb;font-size:16px}*{box-sizing:border-box}body{margin:0}header{padding:28px max(30px,calc((100vw - 1500px)/2));background:#17233b;color:#fff}h1{font-size:30px;margin:0 0 12px}header p{max-width:1180px;line-height:1.7;margin:0;color:#d8e4f8}.bar{position:sticky;top:0;z-index:3;background:#fff;border-bottom:1px solid #d5deea;padding:16px max(30px,calc((100vw - 1500px)/2));display:flex;gap:10px;flex-wrap:wrap}button,select,input{font:inherit;border:1px solid #c8d4e5;background:#fff;padding:10px 14px;border-radius:8px}button{cursor:pointer}button.active{background:#147d70;color:#fff;border-color:#147d70}button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #739bff}main{max-width:1500px;margin:28px auto;padding:0 30px}.notice{border-left:4px solid #147d70;background:#e8f4f0;padding:18px 22px;line-height:1.8}.meta{color:#53647e;font-size:14px;line-height:1.7;margin:18px 0}.entry{background:#fff;border:1px solid #dae2ed;border-radius:12px;padding:24px;margin:18px 0;scroll-margin-top:100px}.entry.user_message{border-left:6px solid #4568d8}.entry.ai_collaboration_prompt{border-left:6px solid #147d70}.entry.test_command{border-left:6px solid #bd7a21}.entry-head{display:flex;justify-content:space-between;gap:20px;align-items:center;flex-wrap:wrap}.entry-head strong{font-size:18px}.pill{font-size:13px;display:inline-block;padding:4px 9px;background:#edf2f9;border-radius:4px;margin-right:7px}.source{font-size:13px;color:#56677f}.entry pre{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.85;font-family:inherit;font-size:16px;margin-bottom:0}.test_command pre{font-family:Consolas,monospace}.empty{padding:50px;text-align:center}.counts{margin-left:auto;align-self:center;color:#52637b;font-size:14px}footer{margin:35px 0;color:#52637b;line-height:1.8}a{color:#1c639e}@media(max-width:700px){main{padding:0 14px}.bar,header{padding:16px}.entry{padding:17px}h1{font-size:25px}}</style>
<header><h1>学脉 · 公开开发证据回放</h1><p>以下内容从本次开发的实际会话记录中筛选，按时间排列。用户原话、公开回复、测试命令与协作元数据分别标注；这是已发生过程的回放，不是现场代码生成。公开文本保留原话，仅移除凭据、认证码、个人邮箱及本机绝对路径。</p></header>
<nav class="bar" aria-label="核心功能证据"><button data-feature="graph">知识图谱与资源联动</button><button data-feature="practice">练习、作业与学习推荐</button><button data-feature="ai">DeepSeek 辅导与检索</button><button data-feature="all">全部记录</button><button id="appendix-button" data-feature="appendix" hidden>可见协作卡片逐字转存</button><select id="kind" aria-label="证据类型"><option value="all">全部证据类型</option><option value="user_message">原始用户指令</option><option value="ai_collaboration_prompt">公开协作 Prompt</option><option value="ai_collaboration_received">公开协作回复</option><option value="assistant_message">Codex 可见回复</option><option value="test_command">实际测试命令</option><option value="ai_collaboration_metadata">协作元数据（正文缺失）</option></select><input id="search" type="search" placeholder="搜索原话，例如：SSE、作业、召回" aria-label="搜索证据"><span class="counts" id="counts"></span></nav>
<main><section class="notice"><strong id="feature-title"></strong><div>两类来源分别标注：自动快照保留公开字段，未取得加密的协作正文；独立附录从本聊天可见协作卡片逐字转存，保存核心功能的 Prompt 与回复，不等同完整原始导出，建议保留原始界面截图交叉核对。测试记录只保留命令和退出码。</div></section><div class="meta" id="snapshot"></div><div id="transcript"></div><div id="entries"></div><footer>本页是本机开发证据查看页，不属于学生或教师产品功能。独立转存原文和自动筛选记录来源不同；正式提交前应与原始界面核对，并检查成片时长、分辨率和至少两分钟 AI 协同过程内容。</footer></main>
<script id="evidence" type="application/json">__DATA__</script><script>
const bundle=JSON.parse(document.getElementById('evidence').textContent), labels={user_message:'原始用户指令',assistant_message:'Codex 可见回复',ai_collaboration_prompt:'公开协作 Prompt',ai_collaboration_received:'公开协作回复',ai_collaboration_metadata:'协作元数据（正文缺失）',ai_collaboration_result:'协作工具回执',test_command:'实际测试命令'}, sourceLabels={root:'主代理',backend:'后端子任务',frontend:'前端子任务',ai:'AI 服务子任务'};
let feature=new URLSearchParams(location.search).get('feature')||(bundle.visible_card_appendix?'appendix':'graph');const entries=document.getElementById('entries'),kind=document.getElementById('kind'),search=document.getElementById('search');document.getElementById('appendix-button').hidden=!bundle.visible_card_appendix;document.getElementById('appendix-button').style.fontWeight='700';
function render(){document.querySelectorAll('[data-feature]').forEach(b=>b.classList.toggle('active',b.dataset.feature===feature));entries.replaceChildren();if(feature==='appendix'&&bundle.visible_card_appendix){document.getElementById('feature-title').textContent='独立附录：可见协作卡片逐字转存';document.getElementById('counts').textContent='独立来源 · 非自动原始导出';const article=document.createElement('article');article.className='entry';const title=document.createElement('h2');title.textContent=bundle.visible_card_appendix.source;const note=document.createElement('p');note.textContent=bundle.visible_card_appendix.verification;const pre=document.createElement('pre');pre.textContent=bundle.visible_card_appendix.text;article.append(title,note,pre);entries.append(article);return}document.getElementById('feature-title').textContent=bundle.features[feature]||'全部公开开发记录';const q=search.value.toLocaleLowerCase();const records=bundle.records.filter(r=>(feature==='all'||r.features.includes(feature))&&(kind.value==='all'||r.kind===kind.value)&&(!q||JSON.stringify(r).toLocaleLowerCase().includes(q)));document.getElementById('counts').textContent=records.length+' 条记录';for(const r of records){const article=document.createElement('article');article.className='entry '+r.kind;article.id=r.id;const head=document.createElement('div');head.className='entry-head';const title=document.createElement('strong');title.textContent=(r.origin==='user_ui_reply'?'用户界面答复（原始结构）':labels[r.kind])+(r.operation?' · '+r.operation:'');const src=document.createElement('span');src.className='source';src.textContent=sourceLabels[r.source]+' · '+new Date(r.timestamp).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})+' · 原始行 '+r.source_line;head.append(title,src);article.append(head);const tag=document.createElement('div');tag.style.marginTop='12px';for(const f of r.features){const p=document.createElement('span');p.className='pill';p.textContent=bundle.features[f];tag.append(p)}article.append(tag);const pre=document.createElement('pre');if(r.text!==undefined)pre.textContent=r.text;else if(r.kind==='test_command')pre.textContent=r.command+'\n退出码：'+r.exitCode;else if(r.arguments)pre.textContent=(r.arguments.target?'接收任务：'+r.arguments.target+'\n':r.arguments.task_name?'创建子任务：'+r.arguments.task_name+'\n':'')+(r.arguments.message||r.notice||'');else pre.textContent=typeof r.result==='string'?r.result:JSON.stringify(r.result,null,2);article.append(pre);entries.append(article)}if(!records.length){const p=document.createElement('p');p.className='empty';p.textContent='此筛选下没有记录，试试其他关键词。';entries.append(p)}}
const baseRender=render;render=function(){baseRender();const container=document.getElementById('transcript');container.replaceChildren();const appendix=bundle.visible_card_appendix,section=appendix?.sections?.[feature];if(!section)return;const article=document.createElement('article');article.className='entry visible-card-transcript';const heading=document.createElement('h2');heading.textContent='本主题的可见协作卡片逐字转存';const note=document.createElement('p');note.textContent=appendix.verification+' 下方另列自动筛选记录，来源不混同。';const pre=document.createElement('pre');pre.textContent=section;article.append(heading,note,pre);container.append(article);document.getElementById('counts').textContent='逐字转存 + '+document.getElementById('counts').textContent;};
document.querySelectorAll('[data-feature]').forEach(b=>b.addEventListener('click',()=>{feature=b.dataset.feature;const url=new URL(location.href);url.searchParams.set('feature',feature);history.replaceState(null,'',url);render();window.scrollTo({top:0})}));kind.addEventListener('change',render);search.addEventListener('input',render);document.getElementById('snapshot').textContent='导出快照：'+new Date(bundle.exported_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})+'（北京时间） · '+bundle.records.length+' 条去重记录 · '+bundle.sources.length+' 个指定来源';render();
</script></html>'''
    return template.replace("__DATA__", data)


def export(sessions_dir: Path, output_dir: Path) -> dict:
    sanitizer = Sanitizer()
    selected = []
    seen = set()
    source_metadata = []
    call_ids = {}
    for source, filename in SOURCE_FILES.items():
        file = sessions_dir / filename
        if not file.is_file():
            raise SystemExit(f"指定的本次来源缺失：{source}；未读取其他会话")
        source_count = 0
        for line_number, line in enumerate(file.open(encoding="utf-8"), 1):
            try:
                raw = json.loads(line)
            except ValueError:
                # A live session may be appending its final line. Earlier
                # complete records are still valid snapshot evidence.
                continue
            for public in select_public(raw, source, line_number, call_ids):
                public = sanitizer.value(public)
                identity = {key: public[key] for key in ("kind", "role", "channel", "text", "operation", "call_id", "arguments", "result", "command", "exitCode") if key in public}
                fingerprint = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                public["id"] = "event-" + fingerprint[:16]
                public["features"] = feature_tags(public)
                selected.append(public)
                source_count += 1
        source_metadata.append({"source": source, "source_file": filename, "exported_records": source_count})
    selected.sort(key=lambda item: (item.get("timestamp") or "", item["source"], item["source_line"]))
    bundle = {
        "title": "学脉本次开发的可见原始记录筛选快照",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "scope": "仅四个显式指定的本次会话；可见消息、三类协作工具元数据/可读回执、实际收到的公开消息正文、测试命令与退出码",
        "authorship": "user_message 为用户发言或界面答复；协作记录为 Codex 自主分工，不改写为人工追问；仅在存储含公开明文时导出正文",
        "redaction": "仅脱敏凭据、一次性认证码、个人邮箱和本机绝对路径；相同继承内容去重；原始行号用于本机核验",
        "excluded": "系统与开发者消息、内部非公开内容、终端原始输出、工具任意数据和其他会话均未导出",
        "evidence_status": "三个完整 Prompt 链尚未取得：协作参数正文和多数接收 Payload 加密，未读取或解密；应补充界面原始对话导出或录屏，禁止补写缺失原文",
        "features": FEATURES,
        "sources": source_metadata,
        "redaction_counts": dict(sanitizer.counts),
        "records": selected,
    }
    if APPENDIX.is_file():
        appendix_text = sanitizer.text(APPENDIX.read_text(encoding="utf-8"))
        headings = list(re.finditer(r"(?m)^## (链一|链二|链三|可核对范围).*", appendix_text))
        sections = {}
        mapping = {"链一": "graph", "链二": "practice", "链三": "ai"}
        for index, match in enumerate(headings):
            if match.group(1) in mapping:
                end = headings[index + 1].start() if index + 1 < len(headings) else len(appendix_text)
                sections[mapping[match.group(1)]] = appendix_text[match.start():end].strip()
        bundle["visible_card_appendix"] = {
            "source": "本聊天可见协作卡片逐字转存，非 rollout 自动导出",
            "source_file": APPENDIX.name,
            "verification": "由主代理从当前聊天可见的协作卡片逐字转存，属于独立来源；不改写为用户追加追问，不等同完整原始导出。建议保留原始界面截图或录屏用于核验。",
            "text": appendix_text,
            "sections": sections,
        }
        bundle["redaction_counts"] = dict(sanitizer.counts)
        bundle["evidence_status"] = "自动导出未取得加密协作正文；独立附录已从本聊天可见协作卡片逐字转存核心功能 Prompt 与回复。两类来源分别标注，独立转存不等同完整自动原始导出，建议保留原始界面截图交叉核对。"
    audit(bundle)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, label in FEATURES.items():
        chain = {**bundle, "title": label, "records": [record for record in selected if name in record["features"]]}
        audit(chain)
        (output_dir / f"{name}-chain.json").write_text(json.dumps(chain, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "visible-records.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    page = build_html(bundle)
    # Scan the page's data too; text is set through textContent, not innerHTML.
    audit(page)
    (output_dir / "index.html").write_text(page, encoding="utf-8")
    manifest = {key: bundle[key] for key in bundle if key not in {"records", "visible_card_appendix"}}
    manifest["visible_card_appendix_available"] = "visible_card_appendix" in bundle
    manifest["record_counts"] = dict(Counter(item["kind"] for item in selected))
    manifest["output_sha256"] = {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in sorted(output_dir.glob("*")) if file.is_file() and file.name != "manifest.json"}
    audit(manifest)
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"records": len(selected), "types": manifest["record_counts"], "redactions": bundle["redaction_counts"], "sources": len(source_metadata)}


def self_test():
    public = {"type": "response_item", "timestamp": "2026-11-03T00:00:00Z", "payload": {"type": "message", "role": "assistant", "phase": "commentary", "content": [{"type": "output_text", "text": "公开进展"}]}}
    assert select_public(public, "root", 1, {})[0]["text"] == "公开进展"
    hidden = {"type": "response_item", "payload": {"type": "message", "role": "assistant", "phase": "analysis", "content": [{"type": "output_text", "text": "PRIVATE_SENTINEL"}]}}
    assert select_public(hidden, "root", 2, {}) == []
    assert select_public({"type": "response_item", "payload": {"type": "reasoning"}}, "root", 3, {}) == []
    assert select_public({"type": "response_item", "payload": {"type": "message", "role": "developer"}}, "root", 4, {}) == []
    sanitizer = Sanitizer()
    text = sanitizer.text("sk-" + "abcdefghijklmnop" + " C:/Users/example/private.md " + "ABCD" + "-EFGH user@example.org")
    audit(text)
    assert "abcdefghijklmnop" not in text and "example" not in text and "ABCD-EFGH" not in text
    audit(sanitizer.text("DEEPSEEK_API_KEY=" + "fakecredentialvalue"))
    assert test_commands(["pwsh", "-Command", "Get-Content file; python -m pytest backend/tests -q; git status"]) == ["python -m pytest backend/tests -q"]
    calls = {}
    prompt = {"type": "response_item", "payload": {"type": "function_call", "namespace": "collaboration", "name": "send_message", "call_id": "abc", "arguments": '{"target":"backend","message":"修复图谱"}'}}
    assert select_public(prompt, "root", 5, calls)[0]["arguments"]["message"] == "修复图谱"
    assert select_public({"type": "response_item", "payload": {"type": "function_call_output", "call_id": "other", "output": "PRIVATE_SENTINEL"}}, "root", 6, calls) == []
    opaque = {"type": "response_item", "payload": {"type": "function_call", "namespace": "collaboration", "name": "send_message", "call_id": "encrypted-call", "arguments": json.dumps({"target": "backend", "message": "gAAAA" + "A" * 60})}}
    exported = select_public(opaque, "root", 7, calls)[0]
    assert exported["kind"] == "ai_collaboration_metadata" and "message" not in exported["arguments"]
    assert select_public({"type": "response_item", "payload": {"type": "agent_message", "content": [{"type": "input_text", "text": "Sender: root\nPayload:\n\n"}]}}, "ai", 8, calls) == []
    assert "gAAAA" not in json.dumps(exported)
    print("导出器自检通过：仅白名单内容、隐藏消息排除、凭据/路径脱敏、测试命令筛选、协作回执范围")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="筛选保存本次学脉开发的公开交互证据，不导出其他会话或内部内容")
    parser.add_argument("--sessions-dir", type=Path, default=Path(os.getenv("USERPROFILE", str(Path.home()))) / ".codex" / "sessions" / "2026" / "11" / "03")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs" / "development-process" / "raw-evidence")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        print(json.dumps(export(args.sessions_dir, args.output_dir), ensure_ascii=False))
