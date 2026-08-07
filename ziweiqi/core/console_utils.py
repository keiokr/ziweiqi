import locale
import re
import sys


_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def configure_stdio():
    """
    让脚本在 Windows GBK/cp936 控制台、管道和批量任务中遇到 emoji/特殊
    Unicode 字符时不崩溃。保留原编码，只把编码错误改为 replace，避免破坏
    上层脚本按本地编码读取 stdout 的行为。
    """
    for stream in (getattr(sys, "stdout", None), getattr(sys, "stderr", None)):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass


def clean_text_for_console(value):
    """
    清洗将要打印到控制台/管道的文本：
    - 去掉 NUL 和不可见控制字符；
    - 对当前 stdout 编码不支持的字符用 ? 替代；
    - 保留换行、制表符和普通中文。
    """
    if value is None:
        return ""
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)

    text = _CONTROL_CHARS_RE.sub("", text)
    encoding = (
        getattr(getattr(sys, "stdout", None), "encoding", None)
        or locale.getpreferredencoding(False)
        or "utf-8"
    )
    try:
        return text.encode(encoding, errors="replace").decode(encoding, errors="replace")
    except Exception:
        return text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")


def safe_print(value="", end="\n", flush=False):
    text = clean_text_for_console(value)
    try:
        print(text, end=end, flush=flush)
    except UnicodeEncodeError:
        fallback_encoding = locale.getpreferredencoding(False) or "utf-8"
        safe = text.encode(fallback_encoding, errors="replace").decode(
            fallback_encoding, errors="replace"
        )
        print(safe, end=end, flush=flush)


def safe_write(value):
    text = clean_text_for_console(value)
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        fallback_encoding = locale.getpreferredencoding(False) or "utf-8"
        sys.stdout.write(
            text.encode(fallback_encoding, errors="replace").decode(
                fallback_encoding, errors="replace"
            )
        )
    sys.stdout.flush()
