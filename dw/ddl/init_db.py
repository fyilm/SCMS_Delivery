"""一键初始化：建库建表(DDL) + 创建最小权限账号 + 生成 config/.env。

用法：
    python dw/ddl/init_db.py            # 从环境变量 MYSQL_ROOT_PWD 读取 root 密码
    python dw/ddl/init_db.py <root密码>

说明：
    - 执行 dw/ddl/schema.sql（7 schema 全量重建）
    - 随机生成 scms_etl / scms_bi / scms_api 三个专用账号密码
    - 授权见 dw/ddl/grants.sql（本脚本按同等权限执行）
    - 凭据写入 config/.env（该文件已 gitignore，不入库）
"""
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_SQL = Path(__file__).parent / "schema.sql"
ENV_PATH = ROOT / "config" / ".env"
MYSQL_BIN = Path(r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe")

HOST = "127.0.0.1"
PORT = 3306


def gen_pwd() -> str:
    # 20 字符随机密码，避免 shell 特殊字符
    return secrets.token_urlsafe(18).replace("-", "x").replace("_", "y")


def run_schema(root_pwd: str) -> None:
    env = dict(os.environ, MYSQL_PWD=root_pwd)
    cmd = [str(MYSQL_BIN), "-h", HOST, "-P", str(PORT), "-uroot", "--default-character-set=utf8mb4"]
    with open(SCHEMA_SQL, "rb") as f:
        proc = subprocess.run(cmd, stdin=f, env=env, capture_output=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr.decode("utf-8", "replace"))
        raise RuntimeError("schema.sql 执行失败")
    print("[1/3] schema.sql 执行完成（7 schema 全量重建）")


def create_users(root_pwd: str, pwds: dict) -> None:
    conn = pymysql.connect(host=HOST, port=PORT, user="root",
                           password=root_pwd, charset="utf8mb4")
    try:
        with conn.cursor() as cur:
            grants = {
                "scms_etl": (
                    "GRANT SELECT,INSERT,UPDATE,DELETE ON `ods`.* TO 'scms_etl'@'localhost';"
                    "GRANT SELECT,INSERT,UPDATE,DELETE ON `dwd`.* TO 'scms_etl'@'localhost';"
                    "GRANT SELECT,INSERT,UPDATE,DELETE ON `dim`.* TO 'scms_etl'@'localhost';"
                    "GRANT SELECT,INSERT,UPDATE,DELETE ON `dws`.* TO 'scms_etl'@'localhost';"
                    "GRANT SELECT,INSERT,UPDATE,DELETE ON `ads`.* TO 'scms_etl'@'localhost';"
                    "GRANT SELECT,INSERT,UPDATE ON `ops`.* TO 'scms_etl'@'localhost';"
                    "GRANT SELECT ON `meta`.* TO 'scms_etl'@'localhost';"
                ),
                "scms_bi": (
                    "GRANT SELECT ON `ads`.* TO 'scms_bi'@'localhost';"
                    "GRANT SELECT ON `dim`.* TO 'scms_bi'@'localhost';"
                ),
                "scms_api": (
                    "GRANT SELECT ON `ads`.* TO 'scms_api'@'localhost';"
                    "GRANT SELECT ON `dim`.* TO 'scms_api'@'localhost';"
                ),
            }
            for user, pwd in pwds.items():
                cur.execute(f"DROP USER IF EXISTS '{user}'@'localhost'")
                cur.execute(f"CREATE USER '{user}'@'localhost' IDENTIFIED BY %s", (pwd,))
                for stmt in grants[user].split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        cur.execute(stmt)
            cur.execute("FLUSH PRIVILEGES")
        conn.commit()
        print("[2/3] 最小权限账号创建并授权完成：scms_etl / scms_bi / scms_api")
    finally:
        conn.close()


def write_env(root_pwd: str, pwds: dict) -> None:
    ENV_PATH.parent.mkdir(exist_ok=True)
    lines = [
        "# SCMS_Delivery 数据库连接配置（本文件已 gitignore，勿提交）",
        f"MYSQL_HOST={HOST}",
        f"MYSQL_PORT={PORT}",
        "MYSQL_ROOT_USER=root",
        f"MYSQL_ROOT_PWD={root_pwd}",
        "MYSQL_ETL_USER=scms_etl",
        f"MYSQL_ETL_PWD={pwds['scms_etl']}",
        "MYSQL_BI_USER=scms_bi",
        f"MYSQL_BI_PWD={pwds['scms_bi']}",
        "MYSQL_API_USER=scms_api",
        f"MYSQL_API_PWD={pwds['scms_api']}",
        "",
    ]
    ENV_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[3/3] 凭据写入 {ENV_PATH}")


def seed_meta(root_pwd: str) -> None:
    """从 information_schema 自动采集表/字段字典，并从 rules.yaml 灌入规则注册表。"""
    import yaml
    conn = pymysql.connect(host=HOST, port=PORT, user="root",
                           password=root_pwd, charset="utf8mb4")
    schemas = ("ods", "dwd", "dim", "dws", "ads", "meta", "ops")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_schema, table_name, table_comment FROM information_schema.tables "
                "WHERE table_schema IN %s",
                (schemas,),
            )
            tables = cur.fetchall()
            for sch, tbl, cmt in tables:
                cur.execute(
                    "INSERT INTO meta.table_dict (schema_name, table_name, layer, table_comment) "
                    "VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE table_comment=VALUES(table_comment)",
                    (sch, tbl, sch, cmt or ""),
                )
            cur.execute(
                "SELECT table_schema, table_name, column_name, data_type, column_comment "
                "FROM information_schema.columns WHERE table_schema IN %s",
                (schemas,),
            )
            for sch, tbl, col, dt, cmt in cur.fetchall():
                cur.execute(
                    "INSERT INTO meta.column_dict (schema_name, table_name, column_name, data_type, column_comment) "
                    "VALUES (%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE column_comment=VALUES(column_comment)",
                    (sch, tbl, col, dt, cmt or ""),
                )
            rules = yaml.safe_load((ROOT / "dw" / "quality" / "rules.yaml").read_text(encoding="utf-8"))
            cur.execute("DELETE FROM meta.dq_rule")
            for r in rules:
                cur.execute(
                    "INSERT INTO meta.dq_rule (rule_id, dimension, level, layer, rule_name, expected, enabled) "
                    "VALUES (%s,%s,%s,%s,%s,%s,1)",
                    (r["id"], r["dimension"], r["level"], r["layer"], r["name"], str(r["expected"])),
                )
        conn.commit()
        print(f"[4/4] 元数据采集完成：表 {len(tables)} 张、规则 {len(rules)} 条")
    finally:
        conn.close()


def main() -> None:
    if len(sys.argv) > 1:
        root_pwd = sys.argv[1]
    else:
        root_pwd = os.environ.get("MYSQL_ROOT_PWD", "").strip()
    if not root_pwd:
        sys.stderr.write("请通过命令行参数或环境变量 MYSQL_ROOT_PWD 提供 root 密码\n")
        sys.exit(1)

    pwds = {u: gen_pwd() for u in ["scms_etl", "scms_bi", "scms_api"]}
    run_schema(root_pwd)
    create_users(root_pwd, pwds)
    write_env(root_pwd, pwds)
    seed_meta(root_pwd)
    print("初始化完成。")


if __name__ == "__main__":
    main()
