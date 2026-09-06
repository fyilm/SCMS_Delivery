-- ============================================================
-- SQL 分析层：由 DWD 物化 DWS(汇总) 与 ADS(应用)，口径对齐 docs/口径文档.md v1.1
-- 由 dw/analytics/refresh_ads.py 以 scms_etl 账号执行（仅 DML）
-- 关键 SQL 技巧：CTE、窗口函数(min-max/Pareto 累计占比)、ROW_NUMBER 中位数
-- ============================================================

-- ---------- DWS：运输方式时效 ----------
DELETE FROM dws.otd_by_mode;
INSERT INTO dws.otd_by_mode
WITH base AS (
  SELECT shipment_mode, delay_days, ot_bool
  FROM dwd.fact_shipment
  WHERE shipment_mode IS NOT NULL
),
agg AS (
  SELECT shipment_mode, COUNT(*) line_cnt, CAST(SUM(ot_bool) AS SIGNED) ot_cnt,
         ROUND(100*AVG(ot_bool),2) otd_pct, ROUND(AVG(delay_days),2) avg_delay
  FROM base GROUP BY shipment_mode
),
ranked AS (
  SELECT shipment_mode, delay_days,
         ROW_NUMBER() OVER (PARTITION BY shipment_mode ORDER BY delay_days) rn,
         COUNT(*) OVER (PARTITION BY shipment_mode) cnt
  FROM base WHERE delay_days IS NOT NULL
),
med AS (
  SELECT shipment_mode, ROUND(AVG(delay_days),2) median_delay
  FROM ranked WHERE rn IN (FLOOR((cnt+1)/2), CEIL((cnt+1)/2)) GROUP BY shipment_mode
),
p95 AS (
  SELECT shipment_mode, ROUND(MAX(delay_days),2) p95_delay
  FROM ranked WHERE rn <= CEIL(0.95*cnt) GROUP BY shipment_mode
)
SELECT a.shipment_mode, a.line_cnt, a.ot_cnt, a.otd_pct, a.avg_delay, m.median_delay, p.p95_delay
FROM agg a LEFT JOIN med m ON a.shipment_mode=m.shipment_mode
LEFT JOIN p95 p ON a.shipment_mode=p.shipment_mode;

-- ---------- DWS：国家维度时效 ----------
DELETE FROM dws.otd_by_country;
INSERT INTO dws.otd_by_country
WITH base AS (
  SELECT country, delay_days, ot_bool
  FROM dwd.fact_shipment WHERE country IS NOT NULL
),
ranked AS (
  SELECT country, delay_days,
         ROW_NUMBER() OVER (PARTITION BY country ORDER BY delay_days) rn,
         COUNT(*) OVER (PARTITION BY country) cnt
  FROM base WHERE delay_days IS NOT NULL
),
med AS (
  SELECT country, ROUND(AVG(delay_days),2) median_delay
  FROM ranked WHERE rn IN (FLOOR((cnt+1)/2), CEIL((cnt+1)/2)) GROUP BY country
)
SELECT b.country, COUNT(*) line_cnt, CAST(SUM(b.ot_bool) AS SIGNED) ot_cnt,
       ROUND(100*AVG(b.ot_bool),2) otd_pct, m.median_delay
FROM base b LEFT JOIN med m ON b.country=m.country
GROUP BY b.country, m.median_delay;

-- ---------- DWS：采购周期分段 ----------
DELETE FROM dws.cycle_summary;
INSERT INTO dws.cycle_summary
WITH cyc AS (
  SELECT 'c1' seg, c1_pq2po d FROM dwd.fact_shipment WHERE c1_pq2po IS NOT NULL
  UNION ALL SELECT 'c2', c2_po2sched FROM dwd.fact_shipment WHERE c2_po2sched IS NOT NULL
  UNION ALL SELECT 'c3', c3_sched2deliv FROM dwd.fact_shipment WHERE c3_sched2deliv IS NOT NULL
  UNION ALL SELECT 'total', c_total FROM dwd.fact_shipment WHERE c_total IS NOT NULL
),
ranked AS (
  SELECT seg, d, ROW_NUMBER() OVER (PARTITION BY seg ORDER BY d) rn, COUNT(*) OVER (PARTITION BY seg) cnt
  FROM cyc
),
med AS (
  SELECT seg, ROUND(AVG(d),2) median_days FROM ranked
  WHERE rn IN (FLOOR((cnt+1)/2), CEIL((cnt+1)/2)) GROUP BY seg
),
p95 AS (
  SELECT seg, ROUND(MAX(d),2) p95_days FROM ranked
  WHERE rn <= CEIL(0.95*cnt) GROUP BY seg
),
cnts AS (
  SELECT seg, CAST(COUNT(*) AS SIGNED) sample_cnt FROM cyc GROUP BY seg
)
SELECT c.seg,
       CASE c.seg WHEN 'c1' THEN '询价→下单' WHEN 'c2' THEN '下单→计划'
                  WHEN 'c3' THEN '计划→交付' ELSE '询价→交付' END,
       c.sample_cnt, m.median_days, p.p95_days
FROM cnts c LEFT JOIN med m ON c.seg=m.seg LEFT JOIN p95 p ON c.seg=p.seg;

-- ---------- DWS：运输方式单位运费 ----------
DELETE FROM dws.unit_freight_by_mode;
INSERT INTO dws.unit_freight_by_mode
WITH base AS (
  SELECT shipment_mode, unit_freight FROM dwd.fact_shipment WHERE unit_freight IS NOT NULL
),
ranked AS (
  SELECT shipment_mode, unit_freight,
         ROW_NUMBER() OVER (PARTITION BY shipment_mode ORDER BY unit_freight) rn,
         COUNT(*) OVER (PARTITION BY shipment_mode) cnt
  FROM base
),
med AS (
  SELECT shipment_mode, ROUND(AVG(unit_freight),2) median_freight FROM ranked
  WHERE rn IN (FLOOR((cnt+1)/2), CEIL((cnt+1)/2)) GROUP BY shipment_mode
),
p90 AS (
  SELECT shipment_mode, ROUND(MAX(unit_freight),2) p90_freight FROM ranked
  WHERE rn <= CEIL(0.90*cnt) GROUP BY shipment_mode
),
cnts AS (
  SELECT shipment_mode, CAST(COUNT(*) AS SIGNED) sample_cnt FROM base GROUP BY shipment_mode
)
SELECT c.shipment_mode, c.sample_cnt, m.median_freight, p.p90_freight
FROM cnts c LEFT JOIN med m ON c.shipment_mode=m.shipment_mode
LEFT JOIN p90 p ON c.shipment_mode=p.shipment_mode;

-- ---------- DWS：月度趋势 ----------
DELETE FROM dws.monthly_summary;
INSERT INTO dws.monthly_summary
SELECT delivery_month, CAST(COUNT(*) AS SIGNED), CAST(SUM(ot_bool) AS SIGNED),
       ROUND(100*AVG(ot_bool),2), SUM(line_value)
FROM dwd.fact_shipment WHERE delivery_month IS NOT NULL
GROUP BY delivery_month;

-- ---------- ADS：供应商评分卡（复刻 scripts/04_supplier.py） ----------
DELETE FROM ads.supplier_scorecard;
INSERT INTO ads.supplier_scorecard
WITH ven AS (
  SELECT vendor, COUNT(*) line_cnt, COUNT(DISTINCT asn_dn_no) asn_cnt,
         100*AVG(ot_bool) otd,
         COALESCE(AVG(CASE WHEN delay_days > 0 THEN delay_days END), 0) avg_late,
         CAST(SUM(CASE WHEN delay_days > 0 THEN 1 ELSE 0 END) AS SIGNED) late_cnt,
         SUM(line_value) total_value
  FROM dwd.fact_shipment GROUP BY vendor
),
scored AS (SELECT * FROM ven WHERE line_cnt >= 10),
norm AS (
  SELECT v.*,
    v.otd AS s_otd,
    CASE WHEN MAX(v.avg_late) OVER () = MIN(v.avg_late) OVER () THEN 100.0
         ELSE (MAX(v.avg_late) OVER () - v.avg_late) / (MAX(v.avg_late) OVER () - MIN(v.avg_late) OVER ()) * 100 END s_delay,
    CASE WHEN MAX(v.total_value) OVER () = MIN(v.total_value) OVER () THEN 100.0
         ELSE (v.total_value - MIN(v.total_value) OVER ()) / (MAX(v.total_value) OVER () - MIN(v.total_value) OVER ()) * 100 END s_value,
    CASE WHEN MAX(v.line_cnt) OVER () = MIN(v.line_cnt) OVER () THEN 100.0
         ELSE (v.line_cnt - MIN(v.line_cnt) OVER ()) / (MAX(v.line_cnt) OVER () - MIN(v.line_cnt) OVER ()) * 100 END s_freq
  FROM scored v
),
sc AS (
  SELECT norm.*, 0.40*s_otd + 0.30*s_delay + 0.20*s_value + 0.10*s_freq AS score FROM norm
),
abc AS (
  SELECT vendor, CASE WHEN cum <= 0.70 THEN 'A' WHEN cum <= 0.90 THEN 'B' ELSE 'C' END abc
  FROM (
    SELECT vendor, SUM(total_value) OVER (ORDER BY total_value DESC) / SUM(total_value) OVER () cum
    FROM ven
  ) t
)
SELECT ROW_NUMBER() OVER (ORDER BY sc.score DESC), sc.vendor, a.abc, sc.line_cnt, sc.asn_cnt,
       ROUND(sc.otd,2), ROUND(sc.avg_late,2), sc.late_cnt, sc.total_value, ROUND(sc.score,2)
FROM sc LEFT JOIN abc a ON sc.vendor = a.vendor;

-- ---------- ADS：ABC 分级汇总 ----------
DELETE FROM ads.abc_summary;
INSERT INTO ads.abc_summary
WITH ven AS (
  SELECT vendor, SUM(line_value) total_value, COUNT(*) line_cnt
  FROM dwd.fact_shipment GROUP BY vendor
),
abc AS (
  SELECT vendor, total_value, line_cnt,
         CASE WHEN SUM(total_value) OVER (ORDER BY total_value DESC) / SUM(total_value) OVER () <= 0.70 THEN 'A'
              WHEN SUM(total_value) OVER (ORDER BY total_value DESC) / SUM(total_value) OVER () <= 0.90 THEN 'B'
              ELSE 'C' END abc
  FROM ven
)
SELECT abc, CAST(COUNT(*) AS SIGNED), CAST(SUM(line_cnt) AS SIGNED), SUM(total_value),
       ROUND(100*SUM(total_value)/(SELECT SUM(total_value) FROM abc),2)
FROM abc GROUP BY abc ORDER BY abc;

-- ---------- ADS：整体 KPI ----------
DELETE FROM ads.otd_summary;
INSERT INTO ads.otd_summary (kpi, kpi_value, kpi_note)
SELECT 'total_lines', CAST(COUNT(*) AS SIGNED), '总交付行数' FROM dwd.fact_shipment
UNION ALL
SELECT 'otd_pct', ROUND(100*AVG(ot_bool),2), '准时率%' FROM dwd.fact_shipment
UNION ALL
SELECT 'late_cnt', CAST(SUM(CASE WHEN delay_days > 0 THEN 1 ELSE 0 END) AS SIGNED), '迟到行数' FROM dwd.fact_shipment
UNION ALL
SELECT 'median_late_days', (
  SELECT ROUND(AVG(d),2) FROM (
    SELECT delay_days d, ROW_NUMBER() OVER (ORDER BY delay_days) rn, COUNT(*) OVER () cnt
    FROM dwd.fact_shipment WHERE delay_days > 0
  ) t WHERE rn IN (FLOOR((cnt+1)/2), CEIL((cnt+1)/2))
), '迟到中位天数(天)'
UNION ALL
SELECT 'p99_late_days', (
  SELECT ROUND(MAX(d),2) FROM (
    SELECT delay_days d, ROW_NUMBER() OVER (ORDER BY delay_days) rn, COUNT(*) OVER () cnt
    FROM dwd.fact_shipment WHERE delay_days > 0
  ) t WHERE rn <= CEIL(0.99*cnt)
), '迟到P99天数(天)';
