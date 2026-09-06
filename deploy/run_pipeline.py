"""一键编排：ingest → refresh_ads → quality → reconcile（fail-fast）。

运行：uv run python deploy/run_pipeline.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STAGES = [
    ("ingest", "dw/etl/ingest.py"),
    ("refresh_ads", "dw/analytics/refresh_ads.py"),
    ("quality", "dw/quality/run.py"),
    ("reconcile", "dw/analytics/reconcile.py"),
]


def main():
    print("=" * 60)
    print("SCMS_Delivery 数据管道开始执行")
    print("=" * 60)
    for name, script in STAGES:
        print(f"\n>>> [{name}] 运行 {script} ...")
        proc = subprocess.run([sys.executable, str(ROOT / script)])
        if proc.returncode != 0:
            print(f"<<< [{name}] 失败（退出码 {proc.returncode}），管道中止")
            sys.exit(proc.returncode)
        print(f"<<< [{name}] 完成")
    print("\n" + "=" * 60)
    print("全部阶段执行成功")
    print("=" * 60)


if __name__ == "__main__":
    main()
