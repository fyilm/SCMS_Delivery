"""数据库连接与配置工具（读取 config/.env，按角色取连接）。"""
import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "config" / ".env"

load_dotenv(ENV_PATH)


def cfg() -> dict:
    return {
        "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
    }


def connect(role: str = "etl") -> pymysql.connections.Connection:
    """role: root / etl / bi / api"""
    c = cfg()
    if role == "root":
        user, pwd = os.environ.get("MYSQL_ROOT_USER", "root"), os.environ.get("MYSQL_ROOT_PWD", "")
    else:
        user = os.environ.get(f"MYSQL_{role.upper()}_USER")
        pwd = os.environ.get(f"MYSQL_{role.upper()}_PWD", "")
    return pymysql.connect(
        host=c["host"], port=c["port"], user=user, password=pwd,
        charset="utf8mb4", autocommit=False,
    )
