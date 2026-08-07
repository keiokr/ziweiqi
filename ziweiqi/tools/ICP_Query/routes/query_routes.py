# -*- coding: utf-8 -*-
"""
查询路由模块
"""
import asyncio

import aiohttp
from aiohttp import web
from aiohttp_socks import ProxyConnector

from load_config import config
from middlewares import jsondump, wj
from mlog import logger
from utils import (
    get_single_query_retry_times,
    is_socks5_proxy_url,
    normalize_proxy_url,
)


routes = web.RouteTableDef()


def get_retry_backoff_seconds():
    return max(0, int(getattr(getattr(config, "system", object()), "retry_backoff_ms", 1500) or 0)) / 1000


def parse_manual_proxy(proxy_value):
    if proxy_value is None or not str(proxy_value).strip():
        return None, None

    manual_proxy = normalize_proxy_url(proxy_value)
    if not manual_proxy:
        return None, "指定代理格式无效，请使用 host:port 或 socks5://host:port"

    if not is_socks5_proxy_url(manual_proxy):
        return None, "仅支持 socks5 代理"

    return manual_proxy, None


async def resolve_proxy(_request):
    if config.proxy.local_ipv6_pool.enable:
        return ""
    return None


async def validate_socks5_proxy(proxy_url):
    timeout = aiohttp.ClientTimeout(total=min(int(config.system.http_client_timeout or 30), 15))
    connector = ProxyConnector.from_url(proxy_url, ssl=False)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        async with session.get(
            "https://www.baidu.com/",
            ssl=False,
            headers={"Accept-Encoding": "identity", "User-Agent": "Mozilla/5.0"},
        ) as response:
            return 200 <= response.status < 500


@jsondump
@routes.post(r"/proxy/validate")
async def validate_proxy(request):
    try:
        data = await request.json()
    except Exception:
        return wj({"code": 400, "message": "请求体格式无效"})

    proxy_url, error_message = parse_manual_proxy(data.get("proxy"))
    if error_message:
        return wj({"code": 400, "message": error_message})

    try:
        ok = await validate_socks5_proxy(proxy_url)
    except Exception as exc:
        logger.warning(f"socks5代理验证失败: {exc}")
        return wj({"code": 500, "message": f"代理不可用: {exc}"})

    if not ok:
        return wj({"code": 500, "message": "代理验证失败"})

    return wj({"code": 200, "message": "代理可用"})


@jsondump
@routes.view(r"/query/{path}")
async def geturl(request):
    path = request.match_info["path"]
    appth = request.app.get("appth", {})
    bappth = request.app.get("bappth", {})

    if path not in appth and path not in bappth:
        return wj({"code": 102, "msg": "不是支持的查询类型"})

    if path not in config.risk_avoidance.allow_type:
        return wj({"code": 102, "msg": "不是支持的查询类型"})

    if request.method == "GET":
        appname = request.query.get("search")
        page_num = request.query.get("pageNum")
        page_size = request.query.get("pageSize")
        proxy_value = request.query.get("proxy")
    else:
        data = await request.json()
        appname = data.get("search")
        page_num = data.get("pageNum")
        page_size = data.get("pageSize")
        proxy_value = data.get("proxy")

    if not appname:
        return wj({"code": 101, "msg": "参数错误, 请指定 search 参数"})

    if any(appname.endswith(suffix) for suffix in config.risk_avoidance.prohibit_suffix):
        return wj({"code": 405, "message": "不允许的查询内容"})

    manual_proxy, proxy_error_message = parse_manual_proxy(proxy_value)
    if proxy_error_message:
        return wj({"code": 400, "message": proxy_error_message})

    retry_times = get_single_query_retry_times()
    data = {"code": 500, "message": "查询失败"}

    for i in range(retry_times):
        current_proxy = manual_proxy
        if current_proxy is None:
            try:
                current_proxy = await resolve_proxy(request)
            except ValueError as exc:
                logger.error(str(exc))
                return wj({"code": 500, "message": str(exc)})

        if path in appth:
            data = await appth.get(path)(appname, page_num, page_size, proxy=current_proxy)
        else:
            data = await bappth.get(path)(appname, proxy=current_proxy)

        if data.get("code", 500) == 200:
            save_history = getattr(config, "history", None) and getattr(config.history, "save_query_history", True)
            if save_history:
                db = request.app.get("db")
                if db:
                    result_count = len(data.get("params", {}).get("list", [])) if path in appth else len(data.get("params", []))
                    db.add_history(path, appname, result_count, data.get("params"))
            return wj(data)

        if data.get("message", "") == "当前访问已被创宇盾拦截":
            logger.warning("当前访问已被创宇盾拦截")
            return wj(data)

        if i < retry_times - 1 and get_retry_backoff_seconds() > 0:
            await asyncio.sleep(get_retry_backoff_seconds() * max(1, min(i + 1, 3)))

    return wj(data)


def setup_query_routes(app):
    app.add_routes(routes)
