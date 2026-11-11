"""本机Whisper转写，音频仅用于当前请求并在结束时删除。"""
import os
from pathlib import Path
import tempfile
import threading
import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from .auth import current_user
from .db import ROOT, database_path

router = APIRouter(prefix='/api/ai/voice', tags=['本地语音'])
_model = None
_lock = threading.Lock()


def normalize_terms(text):
    """仅修正与队列共同出现的栈同音字，保留原转写供核对。"""
    corrected=re.sub(r'[站战棧](?=(?:和|与|、)队列)', '栈', text)
    return corrected, ([{'from':text,'to':corrected,'rule':'栈与队列课程术语'}] if corrected!=text else [])


def model_directory():
    return Path(os.getenv('XUEMAI_WHISPER_MODEL', str(ROOT / '.local/models/faster-whisper-small')))


def transcribe_audio(path):
    global _model
    if not model_directory().joinpath('model.bin').is_file():
        raise HTTPException(503, '请先运行 scripts/setup-voice.ps1 准备本地语音模型')
    try:
        from faster_whisper import WhisperModel
        import av
        with av.open(str(path)) as audio:
            duration = float(audio.duration or 0) / av.time_base
            if duration > 65:
                raise HTTPException(422, '每段语音请控制在60秒以内')
        with _lock:
            if _model is None:
                _model = WhisperModel(str(model_directory()), device='cpu', compute_type='int8', cpu_threads=4, local_files_only=True)
            segments, info = _model.transcribe(str(path), language='zh', beam_size=5, vad_filter=True,
                initial_prompt='数据结构课程术语：栈和队列、入栈、出栈、广度优先搜索、Python函数。',
                hotwords='栈 队列 广度优先搜索 Python')
            result = [{'start': round(segment.start, 2), 'end': round(segment.end, 2), 'text': segment.text.strip()} for segment in segments]
        text = ''.join(segment['text'] for segment in result).strip()
        if not text:
            raise HTTPException(422, '没有识别到清晰语音，请靠近麦克风后重录')
        corrected,edits=normalize_terms(text)
        return {'text': corrected, 'raw_text':text,'term_corrections':edits,'segments': result, 'engine': 'faster-whisper-small', 'local': True, 'language': info.language}
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(503, '请先运行 scripts/setup-voice.ps1 安装本地语音组件')
    except Exception:
        raise HTTPException(422, '音频无法识别，请使用浏览器重新录制')


@router.get('/status')
def status(user=Depends(current_user)):
    return {'ready': model_directory().joinpath('model.bin').is_file(), 'engine': 'faster-whisper-small', 'max_seconds': 60}


@router.post('/transcribe')
async def transcribe(file: UploadFile = File(), user=Depends(current_user)):
    suffix = Path(file.filename or '').suffix.lower()
    if suffix not in {'.webm', '.wav', '.mp3', '.m4a', '.ogg'}:
        raise HTTPException(422, '请上传WebM、WAV、MP3、M4A或OGG语音')
    content = await file.read(8 * 1024 * 1024 + 1)
    await file.close()
    if not content or len(content) > 8 * 1024 * 1024:
        raise HTTPException(422, '语音不能为空或超过8MB')
    directory = database_path().parent / 'voice-temp'
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=suffix, dir=directory, delete=False) as stream:
        path = Path(stream.name)
        stream.write(content)
    try:
        return await run_in_threadpool(transcribe_audio, path)
    finally:
        path.unlink(missing_ok=True)
