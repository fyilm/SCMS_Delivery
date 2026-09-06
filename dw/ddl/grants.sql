-- ============================================================
-- 最小权限账号授权（模板，含占位符；真实密码由 dw/ddl/init_db.py 随机生成并写入 config/.env）
-- 原则：DDL 仅 root；应用账号按 schema 隔离最小授权、读写分离、无 DDL
-- ============================================================

-- 1) 管道账号（ETL + 质量校验 + 对账）：数据层读写，无 DDL
DROP USER IF EXISTS 'scms_etl'@'localhost';
CREATE USER 'scms_etl'@'localhost' IDENTIFIED BY '{{ETL_PWD}}';
GRANT SELECT, INSERT, UPDATE, DELETE ON `ods`.* TO 'scms_etl'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON `dwd`.* TO 'scms_etl'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON `dim`.* TO 'scms_etl'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON `dws`.* TO 'scms_etl'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON `ads`.* TO 'scms_etl'@'localhost';
GRANT SELECT, INSERT, UPDATE ON `ops`.* TO 'scms_etl'@'localhost';
GRANT SELECT ON `meta`.* TO 'scms_etl'@'localhost';

-- 2) BI 只读账号（Power BI 直连）
-- 注：Power BI 的 MySQL 连接器非 SSL 握手不支持 caching_sha2_password，故用 mysql_native_password
DROP USER IF EXISTS 'scms_bi'@'localhost';
CREATE USER 'scms_bi'@'localhost' IDENTIFIED WITH mysql_native_password BY '{{BI_PWD}}';
GRANT SELECT ON `ads`.* TO 'scms_bi'@'localhost';
GRANT SELECT ON `dws`.* TO 'scms_bi'@'localhost';
GRANT SELECT ON `dim`.* TO 'scms_bi'@'localhost';

-- 3) API 只读账号（FastAPI 查询服务）
DROP USER IF EXISTS 'scms_api'@'localhost';
CREATE USER 'scms_api'@'localhost' IDENTIFIED BY '{{API_PWD}}';
GRANT SELECT ON `ads`.* TO 'scms_api'@'localhost';
GRANT SELECT ON `dim`.* TO 'scms_api'@'localhost';

FLUSH PRIVILEGES;
