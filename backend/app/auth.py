import hashlib
import hmac
import secrets
import time
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from .db import get_db

bearer = HTTPBearer(auto_error=False)


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 180000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password, stored):
    try:
        _, salt, expected = stored.split("$")
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 180000).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, AttributeError):
        return False


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials:
        raise HTTPException(401,"请先登录")
    with get_db() as db:
        row = db.execute("SELECT u.id,u.username,u.name,u.role FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.token=? AND s.expires_at>? AND u.active=1",(credentials.credentials,time.time())).fetchone()
        if not row:
            raise HTTPException(401,"登录已过期，请重新登录")
        return dict(row)


def teacher_user(user=Depends(current_user)):
    if user["role"] != "teacher":
        raise HTTPException(403,"此操作需要教师身份")
    return user


def require_course(db, user, course_id):
    course = db.execute("SELECT * FROM courses WHERE id=?",(course_id,)).fetchone()
    if not course:
        raise HTTPException(404,"课程不存在")
    allowed = course["teacher_id"]==user["id"] if user["role"]=="teacher" else db.execute("SELECT 1 FROM classes c JOIN class_members m ON m.class_id=c.id WHERE c.course_id=? AND m.student_id=?",(course_id,user["id"])).fetchone()
    if not allowed:
        raise HTTPException(403,"无权访问此课程")
    return dict(course)


def require_teacher_course(db,user,course_id):
    if user["role"]!="teacher":
        raise HTTPException(403,"此操作需要教师身份")
    return require_course(db,user,course_id)
