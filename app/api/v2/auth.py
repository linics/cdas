"""用户认证 API。"""

import hmac
import base64
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status, Header, Form
from sqlalchemy.orm import Session

from app.config import get_settings
from app.contracts.auth import Token, UserCreate, UserResponse
from app.db import get_db
from app.models import User, UserRole

router = APIRouter()

# === 简化的Token工具函数 ===

def hash_password(password: str) -> str:
    """使用 bcrypt 进行密码哈希。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def _auth_secret() -> str:
    return get_settings().auth_secret_key


def _token_expire_hours() -> int:
    return get_settings().auth_token_expire_hours


def create_token(user_id: int, role: str) -> str:
    """创建简单的Token。"""
    expire = datetime.now(timezone.utc) + timedelta(hours=_token_expire_hours())
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire.isoformat()
    }
    payload_json = json.dumps(payload)
    payload_b64 = base64.b64encode(payload_json.encode()).decode()
    signature = hmac.new(_auth_secret().encode(), payload_b64.encode(), "sha256").hexdigest()
    return f"{payload_b64}.{signature}"


def decode_token(token: str) -> Optional[dict]:
    """解码Token。"""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, signature = parts
        expected_sig = hmac.new(_auth_secret().encode(), payload_b64.encode(), "sha256").hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
        payload_json = base64.b64decode(payload_b64).decode()
        payload = json.loads(payload_json)
        # 检查过期
        exp = datetime.fromisoformat(payload["exp"])
        if datetime.now(timezone.utc) > exp:
            return None
        return payload
    except Exception:
        return None


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """从Token获取当前用户。"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not authorization or not authorization.startswith("Bearer "):
        raise credentials_exception
    
    token = authorization[7:]  # 去掉 "Bearer "
    payload = decode_token(token)
    if not payload:
        raise credentials_exception
    
    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user


def require_teacher(current_user: User = Depends(get_current_user)) -> User:
    """要求教师权限。"""
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要教师权限"
        )
    return current_user


def require_student(current_user: User = Depends(get_current_user)) -> User:
    """要求学生权限。"""
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要学生权限"
        )
    return current_user


# === API 端点 ===

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """用户注册。"""
    # 检查用户名是否已存在
    if get_user_by_username(db, user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )
    
    # 创建用户
    user = User(
        username=user_data.username,
        password_hash=hash_password(user_data.password),
        role=user_data.role,
        name=user_data.name,
        grade=user_data.grade,
        class_name=user_data.class_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(
    username: str = Form(...),
    password: str = Form(...),
    role: Optional[UserRole] = Form(None),
    db: Session = Depends(get_db)
):
    """用户登录，返回Token。"""
    user = get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if role is not None and user.role != role:
        expected = "教师" if role == UserRole.TEACHER else "学生"
        actual = "教师" if user.role == UserRole.TEACHER else "学生"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"账号角色不匹配：你选择了{expected}登录，该账号实际为{actual}账号",
        )
    
    access_token = create_token(user.id, user.role.value)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息。"""
    return current_user
