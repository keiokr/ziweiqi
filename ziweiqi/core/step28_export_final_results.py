import csv
import os
import sqlite3
import time

from step14_sqlite_utils import DB_PATH, RESULTS_DIR, connect_db as open_sqlite_db


def connect_to_db():
    try:
        conn = open_sqlite_db()
        print(f"成功连接到 SQLite 数据库：{DB_PATH}")
        return conn
    except sqlite3.Error as exc:
        print(f"数据库连接失败: {exc}")
        raise SystemExit(1)


def export_urls_to_txt(conn, table_name, output_file):
    try:
        cursor = conn.cursor()
        try:
            cursor.execute(f"SELECT url FROM {table_name}")
            urls = cursor.fetchall()
        finally:
            cursor.close()

        print(f"共获取到 {len(urls)} 条 url 数据")

        with open(output_file, "w", encoding="utf-8") as file:
            for url in urls:
                file.write((url[0] or "") + "\n")

        print(f"成功导出 {table_name} 表中的 url 字段到 {output_file}")
    except sqlite3.Error as exc:
        print(f"导出 url 数据时出错: {exc}")


def export_results_to_csv(conn, table_name, output_file):
    try:
        cursor = conn.cursor()
        try:
            cursor.execute(f"SELECT * FROM {table_name}")
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
        finally:
            cursor.close()

        print(f"共获取到 {len(results)} 条数据")

        if not results:
            print(f"没有数据导出到 CSV 文件 {output_file}")
            return

        # Use UTF-8 BOM so Excel on Windows opens Chinese correctly.
        with open(output_file, "w", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(columns)
            writer.writerows(results)

        print(f"成功导出 {table_name} 表数据到 {output_file}")
    except sqlite3.Error as exc:
        print(f"导出表数据时出错: {exc}")


def main():
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    conn = connect_to_db()
    try:
        web_output_file = os.path.join(RESULTS_DIR, f"资产已去重_{timestamp}_results2.txt")
        results2_output_file = os.path.join(RESULTS_DIR, f"资产已去重_{timestamp}_results2.csv")

        export_urls_to_txt(conn, "results2", web_output_file)
        export_results_to_csv(conn, "results2", results2_output_file)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
