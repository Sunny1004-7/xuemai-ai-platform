"""会话私有附件，保留段落位置，以受控格式向模型提供资料。"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import secrets
import zipfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader

from .auth import current_user, require_course
from .db import database_path, get_db

router = APIRouter(prefix='/api/ai', tags=['AI 附件'])
MAX_BYTES = 8 * 1024 * 1024
SUPPORTED = {'.txt', '.md', '.pdf', '.docx', '.csv', '.png', '.jpg', '.jpeg'}


def attachment_directory():
    directory = database_path().parent / 'ai-attachments'
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def parse_document(content: bytes, suffix: str):
    if suffix in {'.png', '.jpg', '.jpeg'}:
        try:
            with Image.open(io.BytesIO(content)) as image:
                if image.format not in {'PNG', 'JPEG'} or image.width * image.height > 20000000:
                    raise ValueError()
                image.verify()
            return [], 'image/png' if content.startswith(b'\x89PNG') else 'image/jpeg'
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise HTTPException(422, '图片格式或尺寸不支持')
    segments = []
    try:
        if suffix == '.pdf':
            if not content.startswith(b'%PDF-'):
                raise ValueError()
            document = PdfReader(io.BytesIO(content))
            if document.is_encrypted or len(document.pages) > 60:
                raise HTTPException(422, '请上传未加密且不超过60页的PDF')
            segments = [(f'第{index + 1}页', page.extract_text() or '') for index, page in enumerate(document.pages)]
        elif suffix == '.docx':
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if sum(item.file_size for item in archive.infolist()) > 25000000:
                    raise HTTPException(422, 'Word文档展开后过大')
            from docx import Document
            document = Document(io.BytesIO(content))
            segments = [(f'段落{index + 1}', paragraph.text) for index, paragraph in enumerate(document.paragraphs)]
            for table_index, table in enumerate(document.tables):
                segments += [(f'表{table_index + 1}行{index + 1}', ' | '.join(cell.text for cell in row.cells)) for index, row in enumerate(table.rows)]
        else:
            text = content.decode('utf-8-sig')
            if '\x00' in text:
                raise ValueError()
            if suffix == '.csv':
                segments = [(f'第{index + 1}行', ' | '.join(row)) for index, row in enumerate(csv.reader(io.StringIO(text)))]
            else:
                segments = [(f'第{index + 1}段', part) for index, part in enumerate(text.split('\n\n'))]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, '无法解析文件，请检查格式或使用UTF-8文本')
    if sum(len(text) for _, text in segments) > 250000:
        raise HTTPException(422, '文档文字超过25万字，请拆分后上传')
    chunks = []
    for locator, text in segments:
        for index in range(0, len(text), 900):
            part = text[index:index + 900].strip()
            if part:
                chunks.append((locator + (f'·片段{index // 900 + 1}' if len(text) > 900 else ''), part))
    if not chunks:
        raise HTTPException(422, '文档中没有可提取文字，扫描页请以图片上传')
    return chunks, 'application/octet-stream'


def public_attachment(row):
    return {key: row[key] for key in ('id', 'filename', 'media_type', 'bytes', 'status', 'conversation_id', 'created_at')}


def scoped_attachments(db, user, course_id, ids, conversation_id=None, bind=False):
    if len(ids) > 4 or len(ids) != len(set(ids)):
        raise HTTPException(422, '单条消息最多添加4个不同附件')
    result = []
    for attachment_id in ids:
        row = db.execute('SELECT * FROM ai_attachments WHERE id=? AND user_id=? AND course_id=? AND deleted_at IS NULL', (attachment_id, user['id'], course_id)).fetchone()
        if not row or row['conversation_id'] not in (None, conversation_id):
            raise HTTPException(404, '附件不存在或不属于当前会话')
        if bind and not row['conversation_id']:
            db.execute('UPDATE ai_attachments SET conversation_id=? WHERE id=?', (conversation_id, attachment_id))
        result.append(dict(row))
    return result


def image_blocks(attachments):
    return [{'type': 'image_url', 'image_url': {'url': f"data:{row['media_type']};base64," + base64.b64encode((attachment_directory() / row['storage_name']).read_bytes()).decode(), 'detail': 'low'}} for row in attachments if row['media_type'].startswith('image/')]


@router.post('/attachments', status_code=201)
async def upload_attachment(file: UploadFile = File(), course_id: int = Form(), conversation_id: int | None = Form(None), user=Depends(current_user)):
    with get_db() as db:
        require_course(db, user, course_id)
        if conversation_id and not db.execute('SELECT 1 FROM ai_conversations WHERE id=? AND user_id=? AND course_id=?', (conversation_id, user['id'], course_id)).fetchone():
            raise HTTPException(404, '会话不存在')
    filename = Path((file.filename or '附件').replace('\\', '/')).name[:150]
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(422, '支持TXT、Markdown、PDF、DOCX、CSV和PNG/JPEG图片')
    content = await file.read(MAX_BYTES + 1)
    await file.close()
    if not content or len(content) > MAX_BYTES:
        raise HTTPException(422, '请选择不超过8MB的非空文件')
    from starlette.concurrency import run_in_threadpool
    chunks, media_type = await run_in_threadpool(parse_document, content, suffix)
    attachment_id = secrets.token_hex(16)
    storage_name = attachment_id + suffix
    path = attachment_directory() / storage_name
    try:
        path.write_bytes(content)
        with get_db() as db:
            db.execute('INSERT INTO ai_attachments(id,user_id,course_id,conversation_id,filename,media_type,storage_name,bytes,sha256) VALUES(?,?,?,?,?,?,?,?,?)', (attachment_id, user['id'], course_id, conversation_id, filename, media_type, storage_name, len(content), hashlib.sha256(content).hexdigest()))
            db.executemany('INSERT INTO ai_attachment_chunks(attachment_id,locator,content,ordinal) VALUES(?,?,?,?)', [(attachment_id, locator, text, index) for index, (locator, text) in enumerate(chunks)])
            return public_attachment(db.execute('SELECT * FROM ai_attachments WHERE id=?', (attachment_id,)).fetchone())
    except Exception:
        path.unlink(missing_ok=True)
        raise


@router.get('/attachments/{attachment_id}')
def attachment_detail(attachment_id: str, user=Depends(current_user)):
    with get_db() as db:
        row = db.execute('SELECT * FROM ai_attachments WHERE id=? AND user_id=? AND deleted_at IS NULL', (attachment_id, user['id'])).fetchone()
        if not row:
            raise HTTPException(404, '附件已删除或无权访问')
        require_course(db, user, row['course_id'])
        return public_attachment(row) | {'chunks': [dict(chunk) for chunk in db.execute('SELECT id,locator,content FROM ai_attachment_chunks WHERE attachment_id=? ORDER BY ordinal', (attachment_id,))], 'url': f'/api/ai/attachments/{attachment_id}/file'}


@router.get('/attachments/{attachment_id}/file')
def attachment_file(attachment_id: str, user=Depends(current_user)):
    with get_db() as db:
        row = db.execute('SELECT * FROM ai_attachments WHERE id=? AND user_id=? AND deleted_at IS NULL', (attachment_id, user['id'])).fetchone()
        if not row:
            raise HTTPException(404, '附件已删除或无权访问')
        require_course(db, user, row['course_id'])
        return FileResponse(attachment_directory() / row['storage_name'], filename=row['filename'], media_type=row['media_type'])


@router.delete('/attachments/{attachment_id}')
def delete_attachment(attachment_id: str, user=Depends(current_user)):
    with get_db() as db:
        row = db.execute('SELECT * FROM ai_attachments WHERE id=? AND user_id=? AND deleted_at IS NULL', (attachment_id, user['id'])).fetchone()
        if not row:
            raise HTTPException(404, '附件不存在')
        require_course(db, user, row['course_id'])
        db.execute('DELETE FROM ai_attachment_chunks WHERE attachment_id=?', (attachment_id,))
        db.execute("UPDATE ai_attachments SET status='deleted',deleted_at=CURRENT_TIMESTAMP WHERE id=?", (attachment_id,))
    (attachment_directory() / row['storage_name']).unlink(missing_ok=True)
    return {'deleted': True}
