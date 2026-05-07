"""
一键清空脚本 — 删除所有 Qdrant 向量数据 + MySQL documents 表 + 本地 data/ 目录
用法: python nuke_all_data.py
     python nuke_all_data.py --dry-run   (仅预览，不实际删除)
"""
import os
import sys
import shutil
import argparse
import pymysql
import requests
from dotenv import load_dotenv

load_dotenv()

# ── Qdrant 配置 ──────────────────────────────────────
QDRANT_URL  = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_KEY  = os.environ.get("QDRANT_API_KEY", "")
COLLECTIONS = [
    "lightrag_vdb_entities",
    "lightrag_vdb_relationships",
    "lightrag_vdb_chunks",
]

# ── MySQL 配置 ────────────────────────────────────────
MYSQL_HOST  = os.environ.get("MYSQL_HOST")
MYSQL_PORT  = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_USER  = os.environ.get("MYSQL_USER")
MYSQL_PASS  = os.environ.get("MYSQL_PASSWORD")
MYSQL_DB    = os.environ.get("MYSQL_DB", "lightrag_db")

HEADERS = {"api-key": QDRANT_KEY} if QDRANT_KEY else {}


def count_qdrant(col: str) -> int:
    try:
        r = requests.post(
            f"{QDRANT_URL}/collections/{col}/points/count",
            json={},
            headers=HEADERS,
            timeout=10,
        )
        return r.json().get("result", {}).get("count", -1)
    except Exception as e:
        return -1


def delete_qdrant_collection_points(col: str) -> bool:
    """删除集合中所有点（保留集合结构）"""
    # Qdrant 用空 filter 删除所有点
    r = requests.post(
        f"{QDRANT_URL}/collections/{col}/points/delete",
        json={"filter": {}},
        headers=HEADERS,
        timeout=30,
    )
    return r.status_code == 200


def count_mysql_docs() -> int:
    conn = pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASS,
        database=MYSQL_DB, charset="utf8mb4",
    )
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM documents")
        count = cur.fetchone()[0]
    conn.close()
    return count


def delete_mysql_docs():
    conn = pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASS,
        database=MYSQL_DB, charset="utf8mb4",
    )
    with conn.cursor() as cur:
        cur.execute("DELETE FROM documents")
        deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted


DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def list_workspace_dirs() -> list[str]:
    """列出 data/ 下所有 workspace 子目录（dept_* / user_*）"""
    if not os.path.isdir(DATA_DIR):
        return []
    return [
        os.path.join(DATA_DIR, d)
        for d in os.listdir(DATA_DIR)
        if os.path.isdir(os.path.join(DATA_DIR, d))
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="仅预览数量，不实际删除")
    args = parser.parse_args()
    dry = args.dry_run

    print("=" * 55)
    print("💣  NUKE ALL DATA" + ("  [DRY RUN]" if dry else ""))
    print("=" * 55)

    # ── 预览 Qdrant ──────────────────────────────────
    print("\n📦 Qdrant 向量数据:")
    total_vectors = 0
    for col in COLLECTIONS:
        cnt = count_qdrant(col)
        total_vectors += max(cnt, 0)
        status = f"{cnt} 条" if cnt >= 0 else "连接失败"
        print(f"   {col}: {status}")
    print(f"   合计: {total_vectors} 条")

    # ── 预览 MySQL ───────────────────────────────────
    print("\n🗄️  MySQL documents 表:")
    try:
        doc_count = count_mysql_docs()
        print(f"   documents: {doc_count} 条记录")
    except Exception as e:
        print(f"   连接失败: {e}")
        doc_count = -1

    # ── 预览本地 data/ 目录 ───────────────────────────
    ws_dirs = list_workspace_dirs()
    print(f"\n📂 本地 data/ workspace 目录 ({len(ws_dirs)} 个):")
    for d in ws_dirs:
        print(f"   {os.path.basename(d)}/")

    if dry:
        print("\n✅ DRY RUN 结束，未做任何更改。")
        return

    # ── 二次确认 ─────────────────────────────────────
    print()
    confirm = input("⚠️  确认删除所有数据？输入 YES 继续: ").strip()
    if confirm != "YES":
        print("已取消。")
        return

    # ── 删除 Qdrant ──────────────────────────────────
    print("\n🔥 正在清空 Qdrant...")
    for col in COLLECTIONS:
        ok = delete_qdrant_collection_points(col)
        print(f"   {col}: {'✅ 已清空' if ok else '❌ 删除失败'}")

    # ── 删除 MySQL ───────────────────────────────────
    print("\n🔥 正在清空 MySQL documents...")
    try:
        deleted = delete_mysql_docs()
        print(f"   ✅ 已删除 {deleted} 条记录")
    except Exception as e:
        print(f"   ❌ 删除失败: {e}")

    # ── 删除本地 data/ workspace 目录 ────────────────
    print("\n🔥 正在清空本地 data/ workspace 目录...")
    for d in ws_dirs:
        try:
            shutil.rmtree(d)
            print(f"   ✅ 已删除 {os.path.basename(d)}/")
        except Exception as e:
            print(f"   ❌ 删除 {os.path.basename(d)}/ 失败: {e}")

    print("\n✅ 全部完成！")


if __name__ == "__main__":
    main()
