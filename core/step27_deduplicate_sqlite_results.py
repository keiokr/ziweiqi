import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlparse

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from step14_sqlite_utils import DB_PATH, connect_db as open_sqlite_db

IP_BUCKET_THRESHOLD = 200
LONG_TITLE_THRESHOLD = 9

DELETE_RULES = [
    # =========================================================
    # 1. 探活失败 / 工具错误类
    # 只删除明显由扫描工具产生的失败记录，不按 HTTP 状态码泛删
    # =========================================================
    ("DELETE FROM results2 WHERE state_code = '-1' AND hash LIKE '%Hash-Error%'", "删除 Hash-Error 失败记录"),
    ("DELETE FROM results2 WHERE state_code = '-1' AND length = 0", "删除 state_code=-1 且空响应记录"),
    ("DELETE FROM results2 WHERE hash LIKE '%Hash-Error%' AND title IN ('None', 'No Title Found', '')", "删除 Hash-Error 空标题记录"),


    # =========================================================
    # 2. 明确 WAF / 云防护 / 安全产品拦截页
    # 只删明确出现“拦截、阻断、攻击、请求错误、安全防护”等语义的页面
    # 不删除普通 403/404/500，不删除普通 Cloudflare/阿里云/腾讯云等厂商名页面
    # =========================================================
    ("DELETE FROM results2 WHERE title LIKE '%阿里云 Web应用防火墙%'", "删除阿里云 Web应用防火墙页面"),
    ("DELETE FROM results2 WHERE title LIKE '%请求错误 | 云防护%'", "删除请求错误 | 云防护页面"),
    ("DELETE FROM results2 WHERE title LIKE '%云防护%' AND title LIKE '%请求错误%'", "删除云防护请求错误页面"),
    ("DELETE FROM results2 WHERE title LIKE '%Web应用防火墙%' AND title LIKE '%拦截%'", "删除 Web 应用防火墙拦截页"),
    ("DELETE FROM results2 WHERE title LIKE '%Web应用防火墙%' AND title LIKE '%阻断%'", "删除 Web 应用防火墙阻断页"),
    ("DELETE FROM results2 WHERE title LIKE '%Web应用防火墙%' AND title LIKE '%请求错误%'", "删除 Web 应用防火墙请求错误页"),
    ("DELETE FROM results2 WHERE title LIKE '%阻断提示%' AND title LIKE '%拦截%'", "删除阻断提示拦截页"),
    ("DELETE FROM results2 WHERE title LIKE '%阻断提示%' AND title LIKE '%攻击%'", "删除阻断提示攻击页"),
    ("DELETE FROM results2 WHERE title LIKE '%您的请求已被拦截%'", "删除请求被拦截页面"),
    ("DELETE FROM results2 WHERE title LIKE '%访问被拦截%'", "删除访问被拦截页面"),
    ("DELETE FROM results2 WHERE title LIKE '%万网虚机IP访问报错提示%'", "万网虚机IP访问报错提示"),
    ("DELETE FROM results2 WHERE title LIKE '%安全拦截%'", "删除安全拦截页面"),
    ("DELETE FROM results2 WHERE title LIKE '%非法请求%' AND title LIKE '%拦截%'", "删除非法请求拦截页面"),
    ("DELETE FROM results2 WHERE title LIKE '%攻击拦截%'", "删除攻击拦截页面"),
    ("DELETE FROM results2 WHERE title LIKE '%防火墙%' AND title LIKE '%拦截%'", "删除防火墙拦截页面"),
    ("DELETE FROM results2 WHERE title LIKE '%防火墙%' AND title LIKE '%阻断%'", "删除防火墙阻断页面"),
    ("DELETE FROM results2 WHERE title LIKE '%安全防护%' AND title LIKE '%拦截%'", "删除安全防护拦截页面"),
    ("DELETE FROM results2 WHERE title LIKE '%安全防护%' AND title LIKE '%阻断%'", "删除安全防护阻断页面"),
    ("DELETE FROM results2 WHERE title LIKE  '%造成安全威胁%'", "造成安全威胁"),
    ("DELETE FROM results2 WHERE title LIKE  '%请求已被阻断%'", "请求已被阻断"),
    ("DELETE FROM results2 WHERE title LIKE  '%不能直接使用IP访问网站%'", "不能直接使用IP访问网站"),
    ("DELETE FROM results2 WHERE title LIKE  '%网站已到期%'", "网站已到期"),
    ("DELETE FROM results2 WHERE state_code LIKE '%404%' AND title LIKE '%您访问的网站不存在%'", "您访问的网站不存在"),
    ("DELETE FROM results2 WHERE title LIKE  '%可疑请求拦截通知%'", "可疑请求拦截通知"),
    ("DELETE FROM results2 WHERE title LIKE  '%400 The plain HTTP request was sent to HTTPS port%'", "400 requestHTTPS port"),
    ("DELETE FROM results2 WHERE title LIKE  '%aTrust 2.0%'", "aTrust 2.0"),
    # =========================================================
    # 3. Cloudflare / DDoS / CDN Challenge 页面
    # 只删明确 challenge / 验证 / DDoS 防护页
    # 不删除所有 Cloudflare 页面
    # =========================================================
    ("DELETE FROM results2 WHERE title LIKE '%Just a moment...%'", "删除 Cloudflare Just a moment 检查页"),
    ("DELETE FROM results2 WHERE title LIKE '%Attention Required!%' AND title LIKE '%Cloudflare%'", "删除 Cloudflare Attention Required 页面"),
    ("DELETE FROM results2 WHERE title LIKE '%Checking your browser%' AND title LIKE '%Cloudflare%'", "删除 Cloudflare 浏览器检查页"),
    ("DELETE FROM results2 WHERE title LIKE '%DDoS protection by Cloudflare%'", "删除 Cloudflare DDoS 防护页"),
    ("DELETE FROM results2 WHERE title LIKE '%Cloudflare Ray ID%' AND title LIKE '%Attention Required%'", "删除 Cloudflare Ray ID 拦截页"),
    ("DELETE FROM results2 WHERE title LIKE '%DDoS Protection%'", "删除 DDoS Protection 页面"),
    ("DELETE FROM results2 WHERE title LIKE '%DDoS-GUARD%'", "删除 DDoS-GUARD 页面"),
    ("DELETE FROM results2 WHERE title LIKE '%Anti-DDoS%'", "删除 Anti-DDoS 页面"),
    ("DELETE FROM results2 WHERE title LIKE '%访问验证%' AND title LIKE '%安全%'", "删除安全访问验证页面"),
    ("DELETE FROM results2 WHERE title LIKE '%人机验证%' AND title LIKE '%安全%'", "删除安全人机验证页面"),
    ("DELETE FROM results2 WHERE title LIKE '%安全验证%' AND title LIKE '%防护%'", "删除安全防护验证页面"),


    # =========================================================
    # 4. 国内常见 WAF / 安全厂商拦截页
    # 只删明确拦截类，不按厂商名泛删
    # =========================================================
    ("DELETE FROM results2 WHERE title LIKE '%百度云加速%' AND title LIKE '%拦截%'", "删除百度云加速拦截页"),
    ("DELETE FROM results2 WHERE title LIKE '%百度云加速%' AND title LIKE '%错误%'", "删除百度云加速错误页"),
    ("DELETE FROM results2 WHERE title LIKE '%安全狗%' AND title LIKE '%拦截%'", "删除安全狗拦截页"),
    ("DELETE FROM results2 WHERE title LIKE '%网站安全狗%' AND title LIKE '%拦截%'", "删除网站安全狗拦截页"),
    ("DELETE FROM results2 WHERE title LIKE '%云锁%' AND title LIKE '%拦截%'", "删除云锁拦截页"),
    ("DELETE FROM results2 WHERE title LIKE '%创宇盾%' AND title LIKE '%拦截%'", "删除创宇盾拦截页"),
    ("DELETE FROM results2 WHERE title LIKE '%知道创宇%' AND title LIKE '%拦截%'", "删除知道创宇拦截页"),
    ("DELETE FROM results2 WHERE title LIKE '%玄武盾%' AND title LIKE '%拦截%'", "删除玄武盾拦截页"),
    ("DELETE FROM results2 WHERE title LIKE '%长亭雷池%' AND title LIKE '%拦截%'", "删除长亭雷池拦截页"),
    ("DELETE FROM results2 WHERE title LIKE '%雷池%' AND title LIKE '%WAF%' AND title LIKE '%拦截%'", "删除雷池 WAF 拦截页"),
    ("DELETE FROM results2 WHERE title LIKE '%360网站卫士%' AND title LIKE '%拦截%'", "删除 360 网站卫士拦截页"),
    ("DELETE FROM results2 WHERE title LIKE '%腾讯云 Web应用防火墙%' AND title LIKE '%拦截%'", "删除腾讯云 WAF 拦截页"),
    ("DELETE FROM results2 WHERE title LIKE '%腾讯云 Web 应用防火墙%' AND title LIKE '%拦截%'", "删除腾讯云 WAF 拦截页"),
    ("DELETE FROM results2 WHERE title LIKE '%华为云Web应用防火墙%' AND title LIKE '%拦截%'", "删除华为云 WAF 拦截页"),
    ("DELETE FROM results2 WHERE title LIKE '%华为云 WAF%' AND title LIKE '%拦截%'", "删除华为云 WAF 拦截页"),
    ("DELETE FROM results2 WHERE title LIKE '%火山引擎%' AND title LIKE '%访问被拒绝%'", "删除火山引擎访问拒绝页"),
    ("DELETE FROM results2 WHERE title LIKE '%Volcengine%' AND title LIKE '%Forbidden%'", "删除火山引擎 Forbidden 页"),


    # =========================================================
    # 5. CDN / 缓存服务明确错误页
    # 不删除所有 CDN / Tengine / nginx，只删错误代码页
    # =========================================================
    ("DELETE FROM results2 WHERE server LIKE '%VocCache%' AND title LIKE '%错误代码%'", "删除 VocCache 错误代码页"),
    ("DELETE FROM results2 WHERE server LIKE '%Cdn Cache Server%' AND title LIKE '%Error%'", "删除 CDN Error 页面"),
    ("DELETE FROM results2 WHERE server LIKE '%Cdn Cache Server%' AND title LIKE '%错误%'", "删除 CDN 错误页面"),
    ("DELETE FROM results2 WHERE server LIKE '%Tengine%' AND title LIKE '%服务器或网络出错%'", "删除 Tengine 服务器或网络出错页"),
    ("DELETE FROM results2 WHERE server LIKE '%Tengine%' AND title LIKE '%请求错误%'", "删除 Tengine 请求错误页"),


    # =========================================================
    # 6. 域名未备案 / 过期 / 停放 / 出售
    # 注意：不删除“站点不存在 / 未绑定 / 默认占位页”
    # =========================================================
    ("DELETE FROM results2 WHERE title LIKE '%未备案%'", "删除未备案页面"),
    ("DELETE FROM results2 WHERE title LIKE '%Non-compliance%'", "删除 ICP Non-compliance 页面"),
    ("DELETE FROM results2 WHERE title LIKE '%ICP未备案%'", "删除 ICP 未备案页面"),
    ("DELETE FROM results2 WHERE title LIKE '%网站未备案%'", "删除网站未备案页面"),
    ("DELETE FROM results2 WHERE title LIKE '%该网站暂未备案%'", "删除该网站暂未备案页面"),
    ("DELETE FROM results2 WHERE title LIKE '%域名未备案%'", "删除域名未备案页面"),
    ("DELETE FROM results2 WHERE title LIKE '%域名过期%'", "删除域名过期页面"),
    ("DELETE FROM results2 WHERE title LIKE '%域名已过期%'", "删除域名已过期页面"),
    ("DELETE FROM results2 WHERE title LIKE '%域名到期%'", "删除域名到期页面"),
    ("DELETE FROM results2 WHERE title LIKE '%This domain is for sale%'", "删除域名出售页"),
    ("DELETE FROM results2 WHERE title LIKE '%Buy this domain%'", "删除购买域名页"),
    ("DELETE FROM results2 WHERE title LIKE '%Domain parked%'", "删除域名停放页"),
    ("DELETE FROM results2 WHERE title LIKE '%Parking Page%'", "删除域名停放页"),
    ("DELETE FROM results2 WHERE title LIKE '%sedoparking%'", "删除 sedoparking 页面"),
    ("DELETE FROM results2 WHERE title LIKE '%Sedo Domain Parking%'", "删除 Sedo 域名停放页"),


    # =========================================================
    # 7. 邮箱类干扰
    # 如果你也想保留邮箱入口，可以整组注释掉
    # =========================================================
    ("DELETE FROM results2 WHERE title LIKE '%企业邮箱_云邮%'", "删除企业邮箱_云邮"),
    ("DELETE FROM results2 WHERE title LIKE '%阿里邮箱%'", "删除阿里邮箱"),
    ("DELETE FROM results2 WHERE title LIKE '%腾讯邮箱%'", "删除腾讯邮箱"),
    ("DELETE FROM results2 WHERE title LIKE '%网易企业邮箱%'", "删除网易企业邮箱"),
    ("DELETE FROM results2 WHERE title LIKE '%263企业邮箱%'", "删除 263 企业邮箱"),
    ("DELETE FROM results2 WHERE title LIKE '%Coremail邮件系统%'", "删除 Coremail 邮件系统"),
    ("DELETE FROM results2 WHERE title LIKE '%Coremail%邮件%'", "删除 Coremail 邮件页面"),
    ("DELETE FROM results2 WHERE title LIKE '%Webmail%' AND title LIKE '%邮箱%'", "删除 Webmail 邮箱页面"),
    ("DELETE FROM results2 WHERE title LIKE '%webmail%' AND title LIKE '%邮箱%'", "删除 webmail 邮箱页面"),
    ("DELETE FROM results2 WHERE server LIKE '%Tengine%' AND title LIKE '%企业邮箱%'", "删除 Tengine 企业邮箱页面"),


    # =========================================================
    # 8. 明确无效空响应
    # 不删除 No Title 的普通响应，只删空响应
    # =========================================================
    ("DELETE FROM results2 WHERE title = 'None' AND length = 0", "删除 None 空响应"),
    ("DELETE FROM results2 WHERE title = 'No Title Found' AND length = 0", "删除 No Title 空响应"),
    ("DELETE FROM results2 WHERE title = '' AND length = 0", "删除空标题空响应"),
    ("DELETE FROM results2 WHERE title IS NULL AND length = 0", "删除 NULL 标题空响应"),
    ("DELETE FROM results2 WHERE state_code = '0' AND length = 0", "删除状态 0 空响应"),


    # =========================================================
    # 9. 明确垃圾 / 博彩 / SEO 干扰
    # 如果你的目标行业可能包含这些，也可以注释掉
    # =========================================================
    ("DELETE FROM results2 WHERE title LIKE '%nba直播%'", "删除 nba 直播"),
    ("DELETE FROM results2 WHERE title LIKE '%体育官方%'", "删除体育官方"),
    ("DELETE FROM results2 WHERE title LIKE '%体育投注%'", "删除体育投注"),
    ("DELETE FROM results2 WHERE title LIKE '%博彩%' AND title LIKE '%官方%'", "删除博彩官方页"),
    ("DELETE FROM results2 WHERE title LIKE '%彩票%' AND title LIKE '%开奖%'", "删除彩票开奖页"),
    ("DELETE FROM results2 WHERE title LIKE '%六合彩%'", "删除六合彩页面"),
    ("DELETE FROM results2 WHERE title LIKE '%真人娱乐%'", "删除真人娱乐页面"),
    ("DELETE FROM results2 WHERE title LIKE '%百家乐%'", "删除百家乐页面"),
    ("DELETE FROM results2 WHERE title LIKE '%幸运飞艇%'", "删除幸运飞艇页面"),
    ("DELETE FROM results2 WHERE title LIKE '%SEO%' AND title LIKE '%优化%'", "删除 SEO 优化页面"),
    ("DELETE FROM results2 WHERE title LIKE '%站群%' AND title LIKE '%优化%'", "删除站群优化页面"),
]


def connect_to_db():
    try:
        conn = open_sqlite_db()
        conn.row_factory = sqlite3.Row
        print(f"成功连接到 SQLite 数据库：{DB_PATH}")
        return conn
    except sqlite3.Error as exc:
        print(f"数据库连接失败: {exc}")
        raise SystemExit(1)


def execute_delete(conn, query, description):
    cursor = conn.cursor()
    try:
        cursor.execute(query)
        deleted_rows = cursor.rowcount
        conn.commit()
        print(f"{description}: 删除 {deleted_rows} 条记录")
    finally:
        cursor.close()


def remove_large_ip_buckets(conn):
    execute_delete(
        conn,
        f"""
        DELETE FROM results2
        WHERE ip IN (
            SELECT ip
            FROM results2
            WHERE ip IS NOT NULL
            GROUP BY ip
            HAVING COUNT(*) > {IP_BUCKET_THRESHOLD}
        )
        """,
        f"删除出现次数超过 {IP_BUCKET_THRESHOLD} 的 IP 记录",
    )


def dedupe_by_group(conn, columns, label, where=None):
    where_clause = f"WHERE {where}" if where else ""
    tail_clause = f"AND {where}" if where else ""
    execute_delete(
        conn,
        f"""
        DELETE FROM results2
        WHERE rowid NOT IN (
            SELECT keep_rowid
            FROM (
                SELECT MAX(rowid) AS keep_rowid
                FROM results2
                {where_clause}
                GROUP BY {", ".join(columns)}
            )
        )
        {tail_clause}
        """,
        label,
    )


def remove_http_https_duplicates(conn):
    rows = conn.execute(
        """
        SELECT id, url, title, state_code, length, hash, server
        FROM results2
        WHERE url IS NOT NULL AND title IS NOT NULL
        """
    ).fetchall()

    http_keys = set()
    delete_ids = []

    for row in rows:
        parsed = urlparse(row["url"])
        key = (
            parsed.hostname or "",
            parsed.port,
            parsed.path or "/",
            row["title"],
            row["state_code"],
            row["length"],
            row["hash"],
            row["server"],
        )
        if parsed.scheme.lower() == "http":
            http_keys.add(key)

    for row in rows:
        parsed = urlparse(row["url"])
        key = (
            parsed.hostname or "",
            parsed.port,
            parsed.path or "/",
            row["title"],
            row["state_code"],
            row["length"],
            row["hash"],
            row["server"],
        )
        if parsed.scheme.lower() == "https" and key in http_keys:
            delete_ids.append(row["id"])

    if not delete_ids:
        print("删除 HTTP/HTTPS 重复记录: 删除 0 条记录")
        return

    placeholders = ",".join("?" for _ in delete_ids)
    conn.execute(f"DELETE FROM results2 WHERE id IN ({placeholders})", delete_ids)
    conn.commit()
    print(f"删除 HTTP/HTTPS 重复记录: 删除 {len(delete_ids)} 条记录")


def main():
    if not Path(DB_PATH).exists():
        print(f"数据库不存在：{DB_PATH}")
        return 1

    conn = connect_to_db()
    try:
        remove_large_ip_buckets(conn)
        dedupe_by_group(conn, ["port", "hash", "state_code", "title", "length", "server"], "按 port/hash/title 去重")
        dedupe_by_group(conn, ["port", "ip", "state_code", "title", "length", "server"], "按 port/ip/title 去重")
        dedupe_by_group(conn, ["port", "state_code", "title", "length", "hash"], "按 port/state/title/hash 去重")
        dedupe_by_group(
            conn,
            ["ip", "state_code", "title", "server", "length", "hash"],
            "长标题按 ip 去重",
            f"LENGTH(title) > {LONG_TITLE_THRESHOLD}",
        )
        dedupe_by_group(
            conn,
            ["port", "state_code", "title", "server", "length", "hash"],
            "长标题按 port 去重",
            f"LENGTH(title) > {LONG_TITLE_THRESHOLD}",
        )
        dedupe_by_group(
            conn,
            ["ip", "hash", "state_code", "title", "length", "server"],
            "403 页面去重",
            "title LIKE '%403%'",
        )
        dedupe_by_group(
            conn,
            ["ip", "hash", "state_code", "title", "length", "server"],
            "404 页面去重",
            "title LIKE '%404%'",
        )

        for sql, label in DELETE_RULES:
            execute_delete(conn, sql, label)

        remove_http_https_duplicates(conn)
        print("去重完成")
        return 0
    except sqlite3.Error as exc:
        print(f"执行去重时出错: {exc}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
