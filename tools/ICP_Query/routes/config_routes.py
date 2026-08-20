# -*- coding: utf-8 -*-
"""
配置管理路由模块
"""
import asyncio
import os
import shutil
import sys

from aiohttp import web

from middlewares import jsondump, wj
from load_config import config
from mlog import logger
from log_collector import log_collector
from utils import get_batch_keyword_retry_limit, get_batch_query_limit_config, get_network_interfaces, get_resource_path


routes = web.RouteTableDef()


@jsondump
@routes.view(r"/config")
async def get_config(request):
    try:
        config_data = {
            "system": {
                "host": config.system.host,
                "port": config.system.port,
                "http_client_timeout": config.system.http_client_timeout,
                "web_ui": config.system.web_ui,
                "detail_concurrency": max(1, int(getattr(config.system, "detail_concurrency", 1) or 1)),
                "request_interval_ms": getattr(config.system, "request_interval_ms", 1200),
                "retry_backoff_ms": getattr(config.system, "retry_backoff_ms", 1500),
                "batch_keyword_retry_limit": get_batch_keyword_retry_limit(),
                "batch_query_limit": get_batch_query_limit_config(),
            },
            "captcha": {
                "enable": config.captcha.enable,
                "save_failed_img": config.captcha.save_failed_img,
                "save_failed_img_path": config.captcha.save_failed_img_path,
                "retry_times": config.captcha.retry_times,
                "coding_code": getattr(config.captcha, "coding_code", "auto"),
            },
            "proxy": {
                "local_ipv6_pool": {
                    "enable": config.proxy.local_ipv6_pool.enable,
                    "pool_num": config.proxy.local_ipv6_pool.pool_num,
                    "check_interval": config.proxy.local_ipv6_pool.check_interval,
                    "ipv6_network_card": config.proxy.local_ipv6_pool.ipv6_network_card,
                },
                "tunnel": {
                    "enable": False,
                    "url": "",
                },
                "extra_api": {
                    "url": "",
                    "extra_interval": 3,
                    "timeout": 100,
                    "timeout_drop": 8,
                    "check_proxy": False,
                    "proxy_timeout": 0.5,
                    "check_proxy_num": 20,
                    "auto_maintenace": False,
                    "pool_num": 0,
                },
            },
            "risk_avoidance": {
                "allow_type": getattr(config.risk_avoidance, "allow_type", ["web", "app", "mapp", "kapp", "bweb", "bapp", "bmapp", "bkapp"]),
                "prohibit_suffix": getattr(config.risk_avoidance, "prohibit_suffix", []),
            },
            "log": {
                "dir": config.log.dir,
                "file_head": config.log.file_head,
                "backup_count": config.log.backup_count,
                "save_log": config.log.save_log,
                "output_console": config.log.output_console,
            },
            "history": {
                "save_query_history": getattr(config, "history", None) and getattr(config.history, "save_query_history", True)
            },
        }
        return wj({"code": 200, "data": config_data})
    except Exception as exc:
        logger.error(f"读取配置失败: {exc}")
        return wj({"code": 500, "message": f"读取配置失败: {str(exc)}"})


@jsondump
@routes.view(r"/config/save")
async def save_config(request):
    if request.method != "POST":
        return wj({"code": 405, "message": "Method not allowed"})

    try:
        import yaml

        data = await request.json()
        config_dict = {
            "system": {
                "host": data.get("system", {}).get("host", "0.0.0.0"),
                "port": int(data.get("system", {}).get("port", 16181)),
                "http_client_timeout": int(data.get("system", {}).get("http_client_timeout", 30)),
                "web_ui": bool(data.get("system", {}).get("web_ui", True)),
                "detail_concurrency": max(1, int(data.get("system", {}).get("detail_concurrency", 1))),
                "request_interval_ms": max(0, int(data.get("system", {}).get("request_interval_ms", 1200))),
                "retry_backoff_ms": max(0, int(data.get("system", {}).get("retry_backoff_ms", 1500))),
                "batch_keyword_retry_limit": max(1, int(data.get("system", {}).get("batch_keyword_retry_limit", 100))),
                "batch_query_limit": {
                    "enable": bool(data.get("system", {}).get("batch_query_limit", {}).get("enable", True)),
                    "request_interval_ms": max(0, int(data.get("system", {}).get("batch_query_limit", {}).get("request_interval_ms", 6000))),
                    "max_per_minute": max(1, int(data.get("system", {}).get("batch_query_limit", {}).get("max_per_minute", 10))),
                    "window_seconds": max(1, int(data.get("system", {}).get("batch_query_limit", {}).get("window_seconds", 60))),
                },
            },
            "captcha": {
                "enable": bool(data.get("captcha", {}).get("enable", True)),
                "save_failed_img": bool(data.get("captcha", {}).get("save_failed_img", False)),
                "save_failed_img_path": data.get("captcha", {}).get("save_failed_img_path", "faile_captcha"),
                "retry_times": max(1, int(data.get("captcha", {}).get("retry_times", 100))),
                "coding_code": data.get("captcha", {}).get("coding_code", "auto"),
            },
            "proxy": {
                "local_ipv6_pool": {
                    "enable": bool(data.get("proxy", {}).get("local_ipv6_pool", {}).get("enable", False)),
                    "pool_num": int(data.get("proxy", {}).get("local_ipv6_pool", {}).get("pool_num", 88)),
                    "check_interval": int(data.get("proxy", {}).get("local_ipv6_pool", {}).get("check_interval", 1)),
                    "ipv6_network_card": data.get("proxy", {}).get("local_ipv6_pool", {}).get("ipv6_network_card", "eth0"),
                },
                "tunnel": {
                    "enable": False,
                    "url": None,
                },
                "extra_api": {
                    "url": None,
                    "extra_interval": 3,
                    "timeout": 100,
                    "timeout_drop": 8,
                    "check_proxy": False,
                    "proxy_timeout": 0.5,
                    "check_proxy_num": 20,
                    "auto_maintenace": False,
                    "pool_num": 0,
                },
            },
            "risk_avoidance": {
                "allow_type": data.get("risk_avoidance", {}).get("allow_type", ["web", "app", "mapp", "kapp", "bweb", "bapp", "bmapp", "bkapp"]),
                "prohibit_suffix": data.get("risk_avoidance", {}).get("prohibit_suffix", []),
            },
            "log": {
                "dir": data.get("log", {}).get("dir", "logs"),
                "file_head": data.get("log", {}).get("file_head", "ymicp"),
                "backup_count": int(data.get("log", {}).get("backup_count", 7)),
                "save_log": bool(data.get("log", {}).get("save_log", False)),
                "output_console": bool(data.get("log", {}).get("output_console", True)),
            },
            "history": {
                "save_query_history": bool(data.get("history", {}).get("save_query_history", True))
            },
        }

        config_path = get_resource_path("config.yml")
        backup_path = get_resource_path("config.yml.backup")
        if os.path.exists(config_path):
            shutil.copy(config_path, backup_path)

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_dict, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        logger.info("配置文件已更新，需要重启服务生效")
        log_collector.add_log("配置文件已更新，需要重启服务生效")
        return wj({"code": 200, "message": "配置保存成功，重启服务后生效"})
    except Exception as exc:
        logger.error(f"保存配置文件失败: {exc}")
        return wj({"code": 500, "message": f"保存配置失败: {str(exc)}"})


@jsondump
@routes.view(r"/config/network-interfaces")
async def get_network_interfaces_api(request):
    try:
        interfaces = get_network_interfaces()
        return wj({"code": 200, "data": interfaces})
    except Exception as exc:
        logger.error(f"获取网卡列表失败: {exc}")
        return wj({"code": 500, "message": f"获取网卡列表失败: {str(exc)}"})


@jsondump
@routes.view(r"/config/restart")
async def restart_service(request):
    if request.method != "POST":
        return wj({"code": 405, "message": "Method not allowed"})

    try:
        logger.warning("收到重启服务请求，将在 3 秒后重启...")
        log_collector.add_log("收到重启服务请求，将在 3 秒后重启...")

        async def delayed_restart():
            try:
                await asyncio.sleep(3)
                logger.warning("正在重启服务...")
                python = sys.executable
                main_script = sys.argv[0]
                restart_helper = get_resource_path("restart_helper.py")

                if os.name == "nt":
                    import subprocess

                    if os.path.exists(restart_helper):
                        subprocess.Popen(
                            [python, restart_helper],
                            creationflags=subprocess.CREATE_NEW_CONSOLE,
                            cwd=os.path.dirname(get_resource_path(".")),
                        )
                    else:
                        subprocess.Popen([python, main_script], cwd=os.path.dirname(os.path.abspath(main_script)))
                    await asyncio.sleep(1)
                else:
                    os.execv(python, [python] + sys.argv)

                loop = asyncio.get_event_loop()
                for task in asyncio.all_tasks(loop):
                    task.cancel()
                loop.stop()
            except Exception as exc:
                logger.error(f"重启服务时出错: {exc}")

        asyncio.create_task(delayed_restart())
        return wj({"code": 200, "message": "服务将在3秒后重启"})
    except Exception as exc:
        logger.error(f"重启服务失败: {exc}")
        return wj({"code": 500, "message": f"重启服务失败: {str(exc)}"})


def setup_config_routes(app):
    app.add_routes(routes)
