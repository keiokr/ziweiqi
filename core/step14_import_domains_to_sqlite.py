import os
import sqlite3
import time

from encoding_utils import read_lines_guess
from step14_sqlite_utils import DB_PATH, connect_db as open_sqlite_db

def connect_db():
    """连接到 SQLite 数据库"""
    try:
        conn = open_sqlite_db()
        print(f"成功连接到 SQLite 数据库：{DB_PATH}")
        return conn
    except sqlite3.Error as err:
        print(f"数据库连接失败: {err}")
        return None

def create_table_and_field(conn):
    """删除表 results2 并重新创建表和字段"""
    try:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS results2")
        print("表 'results2' 已删除。")

        cursor.execute("""
            CREATE TABLE results2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL
            )
        """)
        print("表 'results2' 已重新创建。")
        conn.commit()
    except sqlite3.Error as err:
        print(f"表操作失败: {err}")

def import_txt_to_db(conn, txt_file):
    """将 .txt 文件中的数据导入到 SQLite 数据库"""
    if not os.path.exists(txt_file):
        print(f"文件 {txt_file} 不存在！")
        return

    try:
        cursor = conn.cursor()
        lines = read_lines_guess(txt_file)

        for line in lines:
            url = line.strip()
            if url:
                cursor.execute("INSERT INTO results2 (url) VALUES (?)", (url,))

        conn.commit()
        print(f"文件 {txt_file} 中的数据已成功导入。")
    except sqlite3.Error as err:
        print(f"插入数据失败: {err}")

def execute_sql_queries(conn):
    """执行删除特定模式的 url 的 SQL 语句"""
    try:
        cursor = conn.cursor()
        
        # 第一条 SQL 语句
        sql1 = """
        DELETE FROM results2
        WHERE url LIKE '%.com.%.cn'
        OR url LIKE '%.com.%.com';
        """
        cursor.execute(sql1)
        conn.commit()
        print("第一条 SQL 执行完成。")

        # 第二条 SQL 语句（保留原逻辑）
        sql2 = """
        DELETE FROM results2
        WHERE url LIKE '%.com.%.blog'
        OR url LIKE '%.com.%.cc'
        OR url LIKE '%.com.%.cn'
        OR url LIKE '%.com.%.com'
        OR url LIKE '%.com.%.net'
        OR url LIKE '%.com.%.org'
        OR url LIKE '%.com.%.org.cn'
        OR url LIKE '%.com.%.site'
        OR url LIKE '%.com.%.tv'
        OR url LIKE '%.blog.%.com'
        OR url LIKE '%.cc.%.com'
        OR url LIKE '%.cn.%.com'
        OR url LIKE '%.com.%.blog'
        OR url LIKE '%.net.%.com'
        OR url LIKE '%.org.%.com'
        OR url LIKE '%.org.cn.%.com'
        OR url LIKE '%.site.%.com'
        OR url LIKE '%.tv.%.com'
        OR url LIKE '%.blog.%.cc'
        OR url LIKE '%.blog.%.cn'
        OR url LIKE '%.blog.%.com'
        OR url LIKE '%.blog.%.net'
        OR url LIKE '%.blog.%.org'
        OR url LIKE '%.blog.%.org.cn'
        OR url LIKE '%.blog.%.site'
        OR url LIKE '%.blog.%.tv'
        OR url LIKE '%.cc.%.blog'
        OR url LIKE '%.cc.%.cn'
        OR url LIKE '%.cc.%.com'
        OR url LIKE '%.cc.%.net'
        OR url LIKE '%.cc.%.org'
        OR url LIKE '%.cc.%.org.cn'
        OR url LIKE '%.cc.%.site'
        OR url LIKE '%.cc.%.tv'
        OR url LIKE '%.cn.%.blog'
        OR url LIKE '%.cn.%.cc'
        OR url LIKE '%.cn.%.com'
        OR url LIKE '%.cn.%.net'
        OR url LIKE '%.cn.%.org'
        OR url LIKE '%.cn.%.org.cn'
        OR url LIKE '%.cn.%.site'
        OR url LIKE '%.cn.%.tv'
        OR url LIKE '%.com.%.cc'
        OR url LIKE '%.com.%.cn'
        OR url LIKE '%.com.%.blog'
        OR url LIKE '%.com.%.net'
        OR url LIKE '%.com.%.org'
        OR url LIKE '%.com.%.org.cn'
        OR url LIKE '%.com.%.site'
        OR url LIKE '%.com.%.tv'
        OR url LIKE '%.net.%.blog'
        OR url LIKE '%.net.%.cc'
        OR url LIKE '%.net.%.cn'
        OR url LIKE '%.net.%.com'
        OR url LIKE '%.net.%.org'
        OR url LIKE '%.net.%.org.cn'
        OR url LIKE '%.net.%.site'
        OR url LIKE '%.net.%.tv'
        OR url LIKE '%.org.%.blog'
        OR url LIKE '%.org.%.cc'
        OR url LIKE '%.org.%.cn'
        OR url LIKE '%.org.%.com'
        OR url LIKE '%.org.%.net'
        OR url LIKE '%.org.%.org.cn'
        OR url LIKE '%.org.%.site'
        OR url LIKE '%.org.%.tv'
        OR url LIKE '%.org.cn.%.blog'
        OR url LIKE '%.org.cn.%.cc'
        OR url LIKE '%.org.cn.%.cn'
        OR url LIKE '%.org.cn.%.com'
        OR url LIKE '%.org.cn.%.net'
        OR url LIKE '%.org.cn.%.org'
        OR url LIKE '%.org.cn.%.site'
        OR url LIKE '%.org.cn.%.tv'
        OR url LIKE '%.site.%.blog'
        OR url LIKE '%.site.%.cc'
        OR url LIKE '%.site.%.cn'
        OR url LIKE '%.site.%.com'
        OR url LIKE '%.site.%.net'
        OR url LIKE '%.site.%.org'
        OR url LIKE '%.site.%.org.cn'
        OR url LIKE '%.site.%.tv'
        OR url LIKE '%.tv.%.blog'
        OR url LIKE '%.tv.%.cc'
        OR url LIKE '%.tv.%.cn'
        OR url LIKE '%.tv.%.com'
        OR url LIKE '%.tv.%.net'
        OR url LIKE '%.tv.%.org'
        OR url LIKE '%.tv.%.org.cn'
        OR url LIKE '%.tv.%.site';
        """
        cursor.execute(sql2)
        conn.commit()
        print("第二条 SQL 执行完成。")
    except sqlite3.Error as err:
        print(f"执行 SQL 查询失败: {err}")

def export_data(conn):
    """导出结果到 23_ziyumingcore_2.txt"""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM results2")
        rows = cursor.fetchall()
        
        output_path = r".\results\tmp\23_ziyumingcore_2.txt"
        with open(output_path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(row[0] + "\n")

        print(f"数据已导出到 {output_path}")
    except sqlite3.Error as err:
        print(f"导出数据失败: {err}")

if __name__ == "__main__":
    conn = connect_db()
    if conn:
        create_table_and_field(conn)
        import_txt_to_db(conn, r".\results\tmp\22_jieguo1.txt")
        execute_sql_queries(conn)
        export_data(conn)
        conn.close()
