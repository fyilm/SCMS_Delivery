-- ============================================================
-- SCMS_Delivery 数据仓库 DDL（一键重建）
-- 分层：ODS(贴源) / DWD(明细) / DIM(维度) / DWS(汇总) / ADS(应用) + meta(元数据) / ops(运行告警)
-- 说明：本文件仅建 schema 与表结构（含 COMMENT 字段字典）；账号授权见 init_db.py（读取 .env，不入库）
-- 字符集：utf8mb4
-- ============================================================

-- ---------- 1. ODS 贴源层 ----------
DROP SCHEMA IF EXISTS `ods`;
CREATE SCHEMA `ods` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE `ods`;

CREATE TABLE `raw_shipment` (
  `id`                     INT NOT NULL COMMENT '原始记录唯一键（源 CSV ID）',
  `project_code`           VARCHAR(64)  DEFAULT NULL COMMENT '项目代码',
  `pq_no`                  VARCHAR(128) DEFAULT NULL COMMENT '采购询价编号（含 Pre-PQ Process 特殊值）',
  `po_so_no`               VARCHAR(64)  DEFAULT NULL COMMENT '采购/销售订单编号',
  `asn_dn_no`              VARCHAR(64)  DEFAULT NULL COMMENT '发货通知/交货单编号',
  `country`                VARCHAR(64)  DEFAULT NULL COMMENT '送达国家',
  `managed_by`             VARCHAR(64)  DEFAULT NULL COMMENT '管理办公室',
  `fulfill_via`            VARCHAR(32)  DEFAULT NULL COMMENT '配送方式（Direct Drop / From RDC）',
  `vendor_inco_term`       VARCHAR(64)  DEFAULT NULL COMMENT '贸易术语（含 N/A - From RDC）',
  `shipment_mode`          VARCHAR(32)  DEFAULT NULL COMMENT '运输方式（含 N/A）',
  `pq_date_raw`            VARCHAR(32)  DEFAULT NULL COMMENT '询价发出日（贴源字符串）',
  `po_date_raw`            VARCHAR(32)  DEFAULT NULL COMMENT '下单日（贴源字符串）',
  `scheduled_date_raw`     VARCHAR(32)  DEFAULT NULL COMMENT '计划交货日（贴源字符串）',
  `delivered_date_raw`     VARCHAR(32)  DEFAULT NULL COMMENT '实际交货日（贴源字符串）',
  `recorded_date_raw`      VARCHAR(32)  DEFAULT NULL COMMENT '录入日（贴源字符串）',
  `product_group`          VARCHAR(32)  DEFAULT NULL COMMENT '产品大类',
  `sub_classification`     VARCHAR(64)  DEFAULT NULL COMMENT '产品细分',
  `vendor`                 VARCHAR(128) DEFAULT NULL COMMENT '供应商',
  `item_description`       VARCHAR(255) DEFAULT NULL COMMENT '品名描述',
  `molecule_test_type`     VARCHAR(128) DEFAULT NULL COMMENT '分子式/检测类型',
  `brand`                  VARCHAR(128) DEFAULT NULL COMMENT '品牌',
  `dosage`                 VARCHAR(64)  DEFAULT NULL COMMENT '剂量强度',
  `dosage_form`            VARCHAR(64)  DEFAULT NULL COMMENT '剂型',
  `uom_raw`                VARCHAR(32)  DEFAULT NULL COMMENT '每包装单位量（贴源字符串）',
  `qty_raw`                VARCHAR(64)  DEFAULT NULL COMMENT '行项目数量（贴源字符串）',
  `line_value_raw`         VARCHAR(64)  DEFAULT NULL COMMENT '行项目总货值（贴源字符串）',
  `pack_price_raw`         VARCHAR(64)  DEFAULT NULL COMMENT '每盒价格（贴源字符串）',
  `unit_price_raw`         VARCHAR(64)  DEFAULT NULL COMMENT '单价（贴源字符串）',
  `manufacturing_site`     VARCHAR(128) DEFAULT NULL COMMENT '生产地点',
  `first_line_designation` VARCHAR(8)   DEFAULT NULL COMMENT '是否一线用药',
  `weight_raw`             VARCHAR(64)  DEFAULT NULL COMMENT '重量（贴源字符串，含 See DN/ASN 引用）',
  `freight_raw`            VARCHAR(128) DEFAULT NULL COMMENT '运费（贴源字符串，含文本标记）',
  `insurance_raw`          VARCHAR(64)  DEFAULT NULL COMMENT '保险费（贴源字符串）',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB COMMENT='ODS 贴源层：SCMS 交付原始记录（字面值原样保留）';

-- ---------- 2. DWD 明细层 ----------
DROP SCHEMA IF EXISTS `dwd`;
CREATE SCHEMA `dwd` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE `dwd`;

CREATE TABLE `fact_shipment` (
  `id`                     INT NOT NULL COMMENT '唯一键',
  `project_code`           VARCHAR(64)  DEFAULT NULL COMMENT '项目代码',
  `pq_no`                  VARCHAR(128) DEFAULT NULL COMMENT '采购询价编号',
  `po_so_no`               VARCHAR(64)  DEFAULT NULL COMMENT '采购/销售订单编号',
  `asn_dn_no`              VARCHAR(64)  DEFAULT NULL COMMENT '发货通知/交货单编号',
  `country`                VARCHAR(64)  DEFAULT NULL COMMENT '送达国家',
  `managed_by`             VARCHAR(64)  DEFAULT NULL COMMENT '管理办公室',
  `fulfill_via`            VARCHAR(32)  DEFAULT NULL COMMENT '配送方式',
  `vendor_inco_term`       VARCHAR(64)  DEFAULT NULL COMMENT '贸易术语',
  `shipment_mode`          VARCHAR(32)  DEFAULT NULL COMMENT '运输方式',
  `pq_date`                DATE         DEFAULT NULL COMMENT '询价发出日（解析后）',
  `po_date`                DATE         DEFAULT NULL COMMENT '下单日（解析后）',
  `scheduled_date`         DATE         DEFAULT NULL COMMENT '计划交货日',
  `delivered_date`         DATE         DEFAULT NULL COMMENT '实际交货日',
  `recorded_date`          DATE         DEFAULT NULL COMMENT '录入日',
  `product_group`          VARCHAR(32)  DEFAULT NULL COMMENT '产品大类',
  `sub_classification`     VARCHAR(64)  DEFAULT NULL COMMENT '产品细分',
  `vendor`                 VARCHAR(128) DEFAULT NULL COMMENT '供应商',
  `item_description`       VARCHAR(255) DEFAULT NULL COMMENT '品名描述',
  `molecule_test_type`     VARCHAR(128) DEFAULT NULL COMMENT '分子式/检测类型',
  `brand`                  VARCHAR(128) DEFAULT NULL COMMENT '品牌',
  `dosage`                 VARCHAR(64)  DEFAULT NULL COMMENT '剂量强度',
  `dosage_form`            VARCHAR(64)  DEFAULT NULL COMMENT '剂型',
  `uom`                    INT          DEFAULT NULL COMMENT '每包装单位量',
  `qty`                    DOUBLE       DEFAULT NULL COMMENT '行项目数量',
  `line_value`             DOUBLE       DEFAULT NULL COMMENT '行项目总货值（USD）',
  `pack_price`             DOUBLE       DEFAULT NULL COMMENT '每盒价格',
  `unit_price`             DOUBLE       DEFAULT NULL COMMENT '单价',
  `manufacturing_site`     VARCHAR(128) DEFAULT NULL COMMENT '生产地点',
  `first_line_designation` VARCHAR(8)   DEFAULT NULL COMMENT '是否一线用药',
  `weight_numeric`         DOUBLE       DEFAULT NULL COMMENT '重量（kg，文本引用已置空）',
  `freight_numeric`        DOUBLE       DEFAULT NULL COMMENT '运费（USD，文本标记已置空）',
  `insurance`              DOUBLE       DEFAULT NULL COMMENT '保险费（USD）',
  `pq_flag`                VARCHAR(16)  DEFAULT NULL COMMENT 'PQ 日期状态：date/pre_pq/not_captured',
  `po_flag`                VARCHAR(16)  DEFAULT NULL COMMENT 'PO 日期状态：date/from_rdc/not_captured',
  `freight_flag`           VARCHAR(16)  DEFAULT NULL COMMENT '运费状态：numeric/included/invoiced/reference',
  `flag_weight_reference`  TINYINT      DEFAULT 0 COMMENT '重量为文本引用（See DN/ASN）',
  `flag_zero_value`        TINYINT      DEFAULT 0 COMMENT '货值为 0',
  `flag_qty_outlier`       TINYINT      DEFAULT 0 COMMENT '数量 IQR×1.5 离群',
  `flag_line_value_outlier` TINYINT     DEFAULT 0 COMMENT '货值 IQR×1.5 离群',
  `flag_pack_price_outlier` TINYINT     DEFAULT 0 COMMENT '每盒价格 IQR×1.5 离群',
  `flag_unit_price_outlier` TINYINT     DEFAULT 0 COMMENT '单价 IQR×1.5 离群',
  `flag_weight_outlier`    TINYINT      DEFAULT 0 COMMENT '重量 IQR×1.5 离群',
  `flag_freight_outlier`   TINYINT      DEFAULT 0 COMMENT '运费 IQR×1.5 离群',
  `flag_insurance_outlier` TINYINT      DEFAULT 0 COMMENT '保险费 IQR×1.5 离群',
  `delay_days`             INT          DEFAULT NULL COMMENT '延迟天数=实际-计划（负值=提前）',
  `ot_bool`                TINYINT      DEFAULT NULL COMMENT '是否准时（delay<=0）',
  `early_bool`             TINYINT      DEFAULT NULL COMMENT '是否提前（delay<0）',
  `c1_pq2po`               INT          DEFAULT NULL COMMENT '周期段1：询价→下单（天）',
  `c2_po2sched`            INT          DEFAULT NULL COMMENT '周期段2：下单→计划（天）',
  `c3_sched2deliv`         INT          DEFAULT NULL COMMENT '周期段3：计划→交付（天）',
  `c_total`                INT          DEFAULT NULL COMMENT '总周期：询价→交付（天）',
  `flag_negative_cycle`    TINYINT      DEFAULT 0 COMMENT '存在负周期',
  `unit_freight`           DOUBLE       DEFAULT NULL COMMENT '单位运费（USD/kg）',
  `flag_unit_freight_extreme` TINYINT    DEFAULT 0 COMMENT '单位运费>10000 USD/kg',
  `delivery_year`          INT          DEFAULT NULL COMMENT '交付年份',
  `delivery_month`         VARCHAR(7)   DEFAULT NULL COMMENT '交付月份（YYYY-MM）',
  PRIMARY KEY (`id`),
  KEY `idx_fact_year` (`delivery_year`),
  KEY `idx_fact_mode` (`shipment_mode`),
  KEY `idx_fact_vendor` (`vendor`),
  KEY `idx_fact_country` (`country`),
  KEY `idx_fact_group` (`product_group`)
) ENGINE=InnoDB COMMENT='DWD 明细层：清洗标准化后的交付明细 + 派生特征';

-- ---------- 3. DIM 维度层 ----------
DROP SCHEMA IF EXISTS `dim`;
CREATE SCHEMA `dim` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE `dim`;

CREATE TABLE `dim_vendor` (
  `vendor`      VARCHAR(128) NOT NULL COMMENT '供应商（自然键）',
  `line_cnt`    INT          DEFAULT NULL COMMENT '交付行数',
  `asn_cnt`     INT          DEFAULT NULL COMMENT '发货单数',
  `first_date`  DATE         DEFAULT NULL COMMENT '首次交付日',
  `last_date`   DATE         DEFAULT NULL COMMENT '最近交付日',
  PRIMARY KEY (`vendor`)
) ENGINE=InnoDB COMMENT='供应商维度';

CREATE TABLE `dim_country` (
  `country`     VARCHAR(64) NOT NULL COMMENT '国家（自然键）',
  `line_cnt`    INT         DEFAULT NULL COMMENT '交付行数',
  `vendor_cnt`  INT         DEFAULT NULL COMMENT '供应商数',
  PRIMARY KEY (`country`)
) ENGINE=InnoDB COMMENT='国家维度';

CREATE TABLE `dim_product_group` (
  `product_group`      VARCHAR(32) NOT NULL COMMENT '产品大类（自然键）',
  `sub_classification` VARCHAR(64) NOT NULL COMMENT '产品细分',
  `line_cnt`           INT         DEFAULT NULL COMMENT '交付行数',
  PRIMARY KEY (`product_group`, `sub_classification`)
) ENGINE=InnoDB COMMENT='产品维度';

CREATE TABLE `dim_date` (
  `cal_date`    DATE        NOT NULL COMMENT '日历日期',
  `cal_year`    SMALLINT    NOT NULL COMMENT '年份',
  `cal_month`   TINYINT     NOT NULL COMMENT '月份',
  `year_month`  VARCHAR(7)  NOT NULL COMMENT 'YYYY-MM',
  `cal_quarter` TINYINT     NOT NULL COMMENT '季度',
  PRIMARY KEY (`cal_date`),
  KEY `idx_date_ym` (`year_month`)
) ENGINE=InnoDB COMMENT='日期维度（由交付日期范围生成）';

-- ---------- 4. DWS 汇总层 ----------
DROP SCHEMA IF EXISTS `dws`;
CREATE SCHEMA `dws` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE `dws`;

CREATE TABLE `otd_by_mode` (
  `shipment_mode` VARCHAR(32) NOT NULL COMMENT '运输方式',
  `line_cnt`      INT         NOT NULL COMMENT '交付行数',
  `ot_cnt`        INT         NOT NULL COMMENT '准时行数',
  `otd_pct`       DECIMAL(6,2) DEFAULT NULL COMMENT '准时率%',
  `avg_delay`     DECIMAL(8,2) DEFAULT NULL COMMENT '平均延迟（天，全样本含负值）',
  `median_delay`  DECIMAL(8,2) DEFAULT NULL COMMENT '延迟中位数（天）',
  `p95_delay`     DECIMAL(8,2) DEFAULT NULL COMMENT '延迟 P95（天）',
  PRIMARY KEY (`shipment_mode`)
) ENGINE=InnoDB COMMENT='DWS 汇总：运输方式维度时效';

CREATE TABLE `otd_by_country` (
  `country`       VARCHAR(64) NOT NULL COMMENT '国家',
  `line_cnt`      INT         NOT NULL COMMENT '交付行数',
  `ot_cnt`        INT         NOT NULL COMMENT '准时行数',
  `otd_pct`       DECIMAL(6,2) DEFAULT NULL COMMENT '准时率%',
  `median_delay`  DECIMAL(8,2) DEFAULT NULL COMMENT '延迟中位数（天）',
  PRIMARY KEY (`country`)
) ENGINE=InnoDB COMMENT='DWS 汇总：国家维度时效';

CREATE TABLE `cycle_summary` (
  `cycle_seg`     VARCHAR(16) NOT NULL COMMENT '周期段：c1/c2/c3/total',
  `seg_desc`      VARCHAR(64) DEFAULT NULL COMMENT '周期段描述',
  `sample_cnt`    INT         NOT NULL COMMENT '有效样本数',
  `median_days`   DECIMAL(8,2) DEFAULT NULL COMMENT '中位数（天）',
  `p95_days`      DECIMAL(8,2) DEFAULT NULL COMMENT 'P95（天）',
  PRIMARY KEY (`cycle_seg`)
) ENGINE=InnoDB COMMENT='DWS 汇总：采购周期分段统计';

CREATE TABLE `unit_freight_by_mode` (
  `shipment_mode`  VARCHAR(32) NOT NULL COMMENT '运输方式',
  `sample_cnt`     INT         NOT NULL COMMENT '有效样本（分子分母均有效）',
  `median_freight` DECIMAL(8,2) DEFAULT NULL COMMENT '单位运费中位数（USD/kg）',
  `p90_freight`    DECIMAL(8,2) DEFAULT NULL COMMENT '单位运费 P90（USD/kg）',
  PRIMARY KEY (`shipment_mode`)
) ENGINE=InnoDB COMMENT='DWS 汇总：运输方式单位运费';

CREATE TABLE `monthly_summary` (
  `year_month`  VARCHAR(7)  NOT NULL COMMENT '交付月份',
  `line_cnt`    INT         NOT NULL COMMENT '交付行数',
  `ot_cnt`      INT         NOT NULL COMMENT '准时行数',
  `otd_pct`     DECIMAL(6,2) DEFAULT NULL COMMENT '准时率%',
  `total_value` DOUBLE       DEFAULT NULL COMMENT '交付金额（USD）',
  PRIMARY KEY (`year_month`)
) ENGINE=InnoDB COMMENT='DWS 汇总：月度趋势';

-- ---------- 5. ADS 应用层 ----------
DROP SCHEMA IF EXISTS `ads`;
CREATE SCHEMA `ads` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE `ads`;

CREATE TABLE `supplier_scorecard` (
  `score_rank`   INT          NOT NULL COMMENT '综合分排名',
  `vendor`       VARCHAR(128) NOT NULL COMMENT '供应商',
  `abc`          CHAR(1)      DEFAULT NULL COMMENT 'ABC 分级',
  `line_cnt`     INT          DEFAULT NULL COMMENT '交付行数',
  `asn_cnt`      INT          DEFAULT NULL COMMENT '发货单数',
  `otd`          DECIMAL(6,2) DEFAULT NULL COMMENT '准时率%',
  `avg_late`     DECIMAL(8,2) DEFAULT NULL COMMENT '平均迟到（仅迟交样本，天）',
  `late_cnt`     INT          DEFAULT NULL COMMENT '迟到行数',
  `total_value`  DOUBLE       DEFAULT NULL COMMENT '交付金额（USD）',
  `score`        DECIMAL(6,2) DEFAULT NULL COMMENT '综合分（0-100）',
  PRIMARY KEY (`vendor`),
  KEY `idx_ads_rank` (`score_rank`)
) ENGINE=InnoDB COMMENT='ADS 应用层：供应商绩效评分卡（>=10 行门槛，权重 40/30/20/10）';

CREATE TABLE `abc_summary` (
  `abc`        CHAR(1)     NOT NULL COMMENT 'ABC 级别',
  `vendor_cnt` INT         NOT NULL COMMENT '供应商数',
  `line_cnt`   INT         NOT NULL COMMENT '交付行数',
  `total_value` DOUBLE     DEFAULT NULL COMMENT '金额（USD）',
  `value_pct`  DECIMAL(6,2) DEFAULT NULL COMMENT '金额占比%',
  PRIMARY KEY (`abc`)
) ENGINE=InnoDB COMMENT='ADS 应用层：ABC 分级汇总（金额帕累托 A<=70% B<=90% C 其余）';

CREATE TABLE `otd_summary` (
  `kpi`           VARCHAR(32) NOT NULL COMMENT 'KPI 名',
  `kpi_value`     DECIMAL(10,2) DEFAULT NULL COMMENT '数值',
  `kpi_note`      VARCHAR(64) DEFAULT NULL COMMENT '说明',
  PRIMARY KEY (`kpi`)
) ENGINE=InnoDB COMMENT='ADS 应用层：整体 KPI（OTD/延迟分位/周期中位等，供 BI 卡片）';

CREATE TABLE `quality_summary` (
  `layer`      VARCHAR(16) NOT NULL COMMENT '分层',
  `dimension`  VARCHAR(16) NOT NULL COMMENT '质量维度：完整性/有效性/一致性/及时性',
  `total_cnt`  INT         NOT NULL COMMENT '规则数',
  `fail_cnt`   INT         NOT NULL COMMENT '失败数',
  `pass_rate`  DECIMAL(6,2) DEFAULT NULL COMMENT '通过率%',
  PRIMARY KEY (`layer`, `dimension`)
) ENGINE=InnoDB COMMENT='ADS 应用层：质量巡检汇总（供 BI 质量页）';

-- ---------- 6. meta 元数据 ----------
DROP SCHEMA IF EXISTS `meta`;
CREATE SCHEMA `meta` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE `meta`;

CREATE TABLE `table_dict` (
  `schema_name` VARCHAR(16)  NOT NULL COMMENT 'schema 名',
  `table_name`  VARCHAR(64)  NOT NULL COMMENT '表名',
  `layer`       VARCHAR(16)  NOT NULL COMMENT '分层',
  `table_comment` VARCHAR(255) DEFAULT NULL COMMENT '表注释',
  PRIMARY KEY (`schema_name`, `table_name`)
) ENGINE=InnoDB COMMENT='元数据：表字典';

CREATE TABLE `column_dict` (
  `schema_name`  VARCHAR(16) NOT NULL COMMENT 'schema 名',
  `table_name`   VARCHAR(64) NOT NULL COMMENT '表名',
  `column_name`  VARCHAR(64) NOT NULL COMMENT '列名',
  `data_type`    VARCHAR(64) DEFAULT NULL COMMENT '数据类型',
  `column_comment` VARCHAR(255) DEFAULT NULL COMMENT '列注释',
  `source_field` VARCHAR(64) DEFAULT NULL COMMENT '来源字段（源 CSV）',
  PRIMARY KEY (`schema_name`, `table_name`, `column_name`)
) ENGINE=InnoDB COMMENT='元数据：字段字典';

CREATE TABLE `dq_rule` (
  `rule_id`     VARCHAR(16)  NOT NULL COMMENT '规则 ID',
  `dimension`   VARCHAR(16)  NOT NULL COMMENT '质量维度',
  `level`       VARCHAR(8)   NOT NULL COMMENT '级别：fatal/warning',
  `layer`       VARCHAR(16)  NOT NULL COMMENT '作用分层',
  `rule_name`   VARCHAR(128) NOT NULL COMMENT '规则名',
  `description` VARCHAR(255) DEFAULT NULL COMMENT '规则说明',
  `expected`    VARCHAR(128) DEFAULT NULL COMMENT '期望值/阈值',
  `enabled`     TINYINT      NOT NULL DEFAULT 1 COMMENT '是否启用',
  PRIMARY KEY (`rule_id`)
) ENGINE=InnoDB COMMENT='元数据：质量校验规则注册表';

-- ---------- 7. ops 运行与告警 ----------
DROP SCHEMA IF EXISTS `ops`;
CREATE SCHEMA `ops` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE `ops`;

CREATE TABLE `run_log` (
  `run_id`     BIGINT       NOT NULL AUTO_INCREMENT COMMENT '运行 ID',
  `run_ts`     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '运行时间',
  `stage`      VARCHAR(32)  NOT NULL COMMENT '阶段：ingest/quality/reconcile/refresh_ads',
  `status`     VARCHAR(16)  NOT NULL COMMENT '状态：success/fail',
  `rows_affected` BIGINT    DEFAULT NULL COMMENT '影响行数',
  `message`    VARCHAR(512) DEFAULT NULL COMMENT '消息',
  PRIMARY KEY (`run_id`)
) ENGINE=InnoDB COMMENT='运行日志';

CREATE TABLE `dq_run_result` (
  `result_id`   BIGINT       NOT NULL AUTO_INCREMENT COMMENT '结果 ID',
  `run_id`      BIGINT       NOT NULL COMMENT '运行 ID（关联 run_log）',
  `rule_id`     VARCHAR(16)  NOT NULL COMMENT '规则 ID（关联 meta.dq_rule）',
  `dimension`   VARCHAR(16)  NOT NULL COMMENT '质量维度',
  `level`       VARCHAR(8)   NOT NULL COMMENT '级别',
  `status`      VARCHAR(8)   NOT NULL COMMENT '结果：pass/fail',
  `actual`      VARCHAR(128) DEFAULT NULL COMMENT '实际值',
  `expected`    VARCHAR(128) DEFAULT NULL COMMENT '期望值',
  `affected_rows` BIGINT     DEFAULT NULL COMMENT '受影响行数',
  `message`     VARCHAR(512) DEFAULT NULL COMMENT '消息',
  `checked_ts`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '校验时间',
  PRIMARY KEY (`result_id`),
  KEY `idx_dq_run` (`run_id`)
) ENGINE=InnoDB COMMENT='质量校验结果明细';

CREATE TABLE `dq_alert` (
  `alert_id`   BIGINT       NOT NULL AUTO_INCREMENT COMMENT '告警 ID',
  `run_id`     BIGINT       NOT NULL COMMENT '运行 ID',
  `rule_id`    VARCHAR(16)  NOT NULL COMMENT '规则 ID',
  `level`      VARCHAR(8)   NOT NULL COMMENT '级别',
  `message`    VARCHAR(512) DEFAULT NULL COMMENT '告警消息',
  `alert_ts`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '告警时间',
  `status`     VARCHAR(16)  DEFAULT 'open' COMMENT '状态：open/resolved',
  PRIMARY KEY (`alert_id`)
) ENGINE=InnoDB COMMENT='质量告警事件表（fatal 级别写入）';

-- ---------- 8. BI / API 取数视图（语义层） ----------
USE `dws`;
CREATE OR REPLACE VIEW `v_otd_by_mode` AS SELECT * FROM `dws`.`otd_by_mode`;
CREATE OR REPLACE VIEW `v_otd_by_country` AS SELECT * FROM `dws`.`otd_by_country`;
CREATE OR REPLACE VIEW `v_cycle_summary` AS SELECT * FROM `dws`.`cycle_summary`;
CREATE OR REPLACE VIEW `v_unit_freight_by_mode` AS SELECT * FROM `dws`.`unit_freight_by_mode`;
CREATE OR REPLACE VIEW `v_monthly_summary` AS SELECT * FROM `dws`.`monthly_summary`;

USE `ads`;
CREATE OR REPLACE VIEW `v_supplier_scorecard` AS SELECT * FROM `ads`.`supplier_scorecard` ORDER BY `score_rank`;
CREATE OR REPLACE VIEW `v_abc_summary` AS SELECT * FROM `ads`.`abc_summary`;
CREATE OR REPLACE VIEW `v_otd_summary` AS SELECT * FROM `ads`.`otd_summary`;
CREATE OR REPLACE VIEW `v_quality_summary` AS SELECT * FROM `ads`.`quality_summary`;
