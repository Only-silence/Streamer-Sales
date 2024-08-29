from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from loguru import logger
from passlib.context import CryptContext
from pydantic import BaseModel

from ...web_configs import WEB_CONFIGS

router = APIRouter(
    prefix="/user",
    tags=["user"],
    responses={404: {"description": "Not found"}},
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/user/login")

# TODO 后续删除！
fake_users_db = {
    "hingwen.wong": {
        "username": "hingwen.wong",
        "user_id": "1",
        "ip_address": "127.0.0.1",
        "email": "peterhuang0323@qq.com",
        "hashed_password": "$2b$12$zXXveodjipHZMoSxJz5ODul7Z9YeRJd0GeSBjpwHdqEtBbAFvEdre",
        "disabled": False,
    }
}


class TokenItem(BaseModel):
    access_token: str
    token_type: str


class UserItem(BaseModel):
    username: str  # User 识别号，用于区分不用的用户调用
    password: str  # 请求 ID，用于生成 TTS & 数字人


class UserInfo(BaseModel):
    username: str
    user_id: int
    ip_adress: str | None = None
    disabled: bool | None = None
    full_name: str | None = None
    email: str | None = None
    hashed_password: str | None = None


PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    logger.info(f"expect password = {PWD_CONTEXT.hash('123456')}")
    return PWD_CONTEXT.verify(plain_password, hashed_password)


def get_password_hash(password):
    return PWD_CONTEXT.hash(password)


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInfo(**user_dict)
    return None


def authenticate_user(db_name, username: str, password: str):
    # 获取用户信息
    user_info = get_user(db_name, username)
    if not user_info:
        # 没有找到用户名
        logger.info(f"Cannot find username = {username}")
        return False

    # 校验密码
    if not verify_password(password, user_info.hashed_password):
        logger.info(f"verify_password fail")
        # 密码校验失败
        return False

    return user_info


def get_current_user_info(token: str = Depends(oauth2_scheme)):
    logger.info(token)
    try:
        token_data = jwt.decode(token, WEB_CONFIGS.TOKEN_JWT_SECURITY_KEY, algorithms=WEB_CONFIGS.TOKEN_JWT_ALGORITHM)
        logger.info(token_data)
        user_id = token_data.get("user_id", None)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    if not user_id:
        logger.error(f"can not get user_id: {user_id}")
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    logger.info(f"Got user_id: {user_id}")
    return user_id


@router.post("/login", summary="登录接口")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):

    # 校验用户名和密码
    user_info = authenticate_user(fake_users_db, form_data.username, form_data.password)

    if not user_info:
        raise HTTPException(status_code=401, detail="Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})

    # 过期时间
    token_expires = datetime.now(timezone.utc) + timedelta(days=7)

    # token 生成包含内容，记录 IP 的原因是防止被其他人拿到用户的 token 进行假冒访问
    token_data = {
        "user_id": user_info.user_id,
        "username": user_info.username,
        "exp": int(token_expires.timestamp()),
        "ip": user_info.ip_adress,
        "login_time": int(datetime.now(timezone.utc).timestamp()),
    }
    logger.info(f"token_data = {token_data}")

    # 生成 token
    token = jwt.encode(token_data, WEB_CONFIGS.TOKEN_JWT_SECURITY_KEY, algorithm=WEB_CONFIGS.TOKEN_JWT_ALGORITHM)

    # 返回
    res_json = TokenItem(access_token=token, token_type="bearer")
    logger.info(f"Got token info = {res_json}")
    # return make_return_data(True, ResultCode.SUCCESS, "成功", content)
    return res_json
