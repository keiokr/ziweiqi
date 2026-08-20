import os
import re
import sqlite3
from urllib.parse import urlsplit


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
DB_PATH = os.path.join(RESULTS_DIR, "results2.db")


def _regexp(pattern, value):
    if value is None:
        return 0
    return 1 if re.search(pattern, value) else 0


def _url_host(url):
    if not url:
        return ""
    return urlsplit(url).netloc


def connect_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.create_function("REGEXP", 2, _regexp)
    conn.create_function("URL_HOST", 1, _url_host)
    return conn
