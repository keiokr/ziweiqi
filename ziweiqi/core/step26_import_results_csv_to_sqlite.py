import csv
import io
import os
import sqlite3
from pathlib import Path

from step14_sqlite_utils import DB_PATH, RESULTS_DIR, connect_db as open_sqlite_db

STRICT_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk")
MOJIBAKE_MARKERS = (
    "鎴",
    "愬",
    "姛",
    "杩",
    "炴",
    "帴",
    "鍒",
    "鏁",
    "鎹",
    "搴",
    "瀵",
    "鍑",
    "閿",
    "鏇",
    "鏃",
    "琛",
)


def connect_to_db():
    try:
        conn = open_sqlite_db()
        print(f"成功连接到 SQLite 数据库：{DB_PATH}")
        return conn
    except sqlite3.Error as exc:
        print(f"数据库连接失败: {exc}")
        raise SystemExit(1)


def drop_table(conn, table_name):
    try:
        cursor = conn.cursor()
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        finally:
            cursor.close()
        conn.commit()
        print(f"成功删除表 {table_name}")
    except sqlite3.Error as exc:
        print(f"删除表时出错: {exc}")


def create_table(conn, table_name):
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        no INTEGER,
        url TEXT,
        ip TEXT,
        port INTEGER,
        state TEXT,
        state_code TEXT,
        title TEXT,
        server TEXT,
        length TEXT,
        hash TEXT,
        other TEXT
    );
    """
    try:
        cursor = conn.cursor()
        try:
            cursor.execute(create_sql)
        finally:
            cursor.close()
        conn.commit()
        print(f"成功创建表 {table_name}")
    except sqlite3.Error as exc:
        print(f"创建表时出错: {exc}")


def score_decoded_text(text):
    cjk_count = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    replacement_count = text.count("\ufffd")
    mojibake_count = sum(text.count(marker) for marker in MOJIBAKE_MARKERS)
    null_count = text.count("\x00")
    return (cjk_count * 4) - (replacement_count * 50) - (mojibake_count * 20) - (null_count * 20)


def read_csv_text(csv_file):
    raw = Path(csv_file).read_bytes()
    candidates = []

    for encoding in STRICT_ENCODINGS:
        try:
            text = raw.decode(encoding)
            candidates.append((score_decoded_text(text), text, encoding, False))
        except UnicodeDecodeError:
            continue

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        _, text, encoding, used_fallback = candidates[0]
        return text, encoding, used_fallback

    fallback_candidates = []
    for encoding in ("gb18030", "gbk", "utf-8"):
        text = raw.decode(encoding, errors="replace")
        fallback_candidates.append((score_decoded_text(text), text, f"{encoding}-replace", True))

    fallback_candidates.sort(key=lambda item: item[0], reverse=True)
    _, text, encoding, used_fallback = fallback_candidates[0]
    return text, encoding, used_fallback


def import_csv_to_db(conn, table_name, csv_file):
    records_imported = 0
    skipped_rows = 0

    try:
        text, encoding_used, used_fallback = read_csv_text(csv_file)
        if used_fallback:
            print(f"警告：{csv_file} 无法按常见编码完整解码，已使用 {encoding_used} 继续导入")
        else:
            print(f"读取 CSV 编码：{encoding_used}")

        reader = csv.reader(io.StringIO(text))
        cursor = conn.cursor()
        try:
            insert_sql = f"""
            INSERT INTO {table_name} (no, url, ip, port, state, state_code, title, server, length, hash, other)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            for row in reader:
                if row[:2] == ["no", "url"]:
                    continue

                if len(row) != 11:
                    skipped_rows += 1
                    continue

                cursor.execute(insert_sql, row)
                records_imported += 1
        finally:
            cursor.close()

        conn.commit()
        print(f"成功将 {records_imported} 条记录从 {csv_file} 导入到 {table_name}")
        if skipped_rows:
            print(f"提示：跳过了 {skipped_rows} 行字段数不为 11 的数据")
    except FileNotFoundError:
        print(f"导入 CSV 数据时出错: 文件不存在 {csv_file}")
    except Exception as exc:
        print(f"导入 CSV 数据时出错: {exc}")


def update_ports(conn, table_name):
    try:
        cursor = conn.cursor()
        try:
            update_sql = f"""
            UPDATE {table_name}
            SET port = 80
            WHERE port IN (80, 443);
            """
            cursor.execute(update_sql)
        finally:
            cursor.close()
        conn.commit()
        print(f"成功更新 {table_name} 表中 port 字段为 80")
    except sqlite3.Error as exc:
        print(f"更新 port 字段时出错: {exc}")


def main():
    conn = connect_to_db()
    try:
        table_name = "results2"
        drop_table(conn, table_name)
        create_table(conn, table_name)

        csv_file = os.path.join(RESULTS_DIR, "results2.csv")
        import_csv_to_db(conn, table_name, csv_file)
        update_ports(conn, table_name)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
