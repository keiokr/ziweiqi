# -*- coding: utf-8 -*-
"""
批量查询任务路由模块
"""
import asyncio
import json
import os
import sys
from datetime import datetime

from aiohttp import web

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from encoding_utils import read_text_guess

from load_config import config
from log_collector import log_collector
from middlewares import jsondump, wj
from mlog import logger
from utils import (
    get_batch_keyword_retry_limit,
    get_batch_query_limit_config,
    get_batch_retry_delay_seconds,
    get_effective_batch_step_delay_seconds,
    is_socks5_proxy_url,
    normalize_proxy_url,
)


routes = web.RouteTableDef()


def parse_manual_proxy(proxy_value):
    if proxy_value is None or not str(proxy_value).strip():
        return None, None

    manual_proxy = normalize_proxy_url(proxy_value)
    if not manual_proxy:
        return None, "指定代理格式无效，请使用 host:port 或 socks5://host:port"

    if not is_socks5_proxy_url(manual_proxy):
        return None, "仅支持 socks5 代理"

    return manual_proxy, None


async def resolve_proxy(_request, manual_proxy=None):
    if manual_proxy:
        logger.info(f"批量任务使用指定代理：{manual_proxy}")
        return manual_proxy

    if config.proxy.local_ipv6_pool.enable:
        return ""

    return None


async def invoke_query(appth, bappth, apptype, keyword, page_num=None, page_size=None, proxy=None):
    if apptype in bappth:
        return await bappth.get(apptype)(keyword, proxy=proxy)
    return await appth.get(apptype)(keyword, pageNum=page_num, pageSize=page_size, proxy=proxy)


async def collect_query_result(appth, bappth, apptype, keyword, proxy, taskname):
    if apptype in ["bapp", "bweb", "bkapp", "bmapp"]:
        return await invoke_query(appth, bappth, apptype, keyword, proxy=proxy)

    page_num = 1
    page_size = 26
    all_results = []
    data = {"code": 200, "params": {"list": [], "total": 0}}

    while True:
        data = await invoke_query(appth, bappth, apptype, keyword, page_num=page_num, page_size=page_size, proxy=proxy)
        if data.get("code") != 200:
            return data

        current_list = data.get("params", {}).get("list", [])
        if not current_list:
            break

        all_results.extend(current_list)
        total = data.get("params", {}).get("total", 0)
        if len(all_results) >= total or len(current_list) < page_size:
            logger.info(f"批量任务 {taskname} - {keyword}: 共获取 {len(all_results)} 条记录")
            break

        page_num += 1
        logger.info(f"批量任务 {taskname} - {keyword}: 已获取 {len(all_results)}/{total} 条记录")

    if data.get("params"):
        data["params"]["list"] = all_results
        data["params"]["total"] = len(all_results)
    else:
        data = {"code": 200, "params": {"list": all_results, "total": len(all_results)}}
    return data


async def create_task(taskname, keywords, request, apptype="web", manual_proxy=None):
    appth = request.app.get("appth", {})
    bappth = request.app.get("bappth", {})

    task = type("Task", (), {
        "curpro": 0,
        "numpro": len(keywords),
        "domains": [],
        "query_keywords": [],
        "appname": apptype,
        "cancelled": False,
        "completed": False,
        "manual_proxy": manual_proxy,
    })()

    request.app["tasks"][taskname] = task

    async def append_empty_result(keyword):
        if apptype in ["app", "mapp", "kapp"]:
            task.domains.append([{
                "cityId": None,
                "countyId": None,
                "dataId": None,
                "leaderName": None,
                "mainId": None,
                "mainLicence": None,
                "mainUnitAddress": None,
                "mainUnitCertNo": None,
                "mainUnitCertType": None,
                "natureId": None,
                "natureName": None,
                "provinceId": None,
                "serviceId": None,
                "serviceLicence": None,
                "serviceName": keyword,
                "serviceType": None,
                "unitName": None,
                "updateRecordTime": None,
                "version": None,
            }])
        elif apptype in ["bapp", "bweb", "bkapp", "bmapp"]:
            task.domains.append([{"blacklistLevel": None, "serviceName": keyword}])
        else:
            task.domains.append([])

    async def process_keyword(keyword):
        retry_limit = get_batch_keyword_retry_limit()
        last_data = {"code": 500, "message": "查询失败"}

        for retry_index in range(1, retry_limit + 1):
            if task.cancelled:
                return

            try:
                proxy = await resolve_proxy(request, task.manual_proxy)
                last_data = await collect_query_result(appth, bappth, apptype, keyword, proxy, taskname)
            except Exception as exc:
                last_data = {"code": 500, "message": str(exc)}
                logger.error(f"处理任务 {keyword} 时发生异常: {exc}")

            if last_data.get("code") == 200:
                task.curpro += 1
                task.query_keywords.append(keyword)
                result_list = last_data.get("params", {}).get("list", [])

                if len(result_list) == 0:
                    await append_empty_result(keyword)
                else:
                    if apptype in ["bapp", "bweb", "bkapp", "bmapp"]:
                        task.domains.append(last_data["params"])
                    else:
                        task.domains.append(result_list)
                return

            if last_data.get("message", "") == "当前访问已被创宇盾拦截":
                logger.warning(f"批量任务 {taskname} - {keyword}: 当前访问已被创宇盾拦截")

            if retry_index < retry_limit:
                wait_seconds = get_batch_retry_delay_seconds(retry_index)
                logger.info(
                    f"批量任务 {taskname} - {keyword}: 第 {retry_index}/{retry_limit} 次失败，"
                    f"等待 {wait_seconds} 秒后重试"
                )
                await asyncio.sleep(wait_seconds)

        logger.warning(f"任务 {keyword} 达到最大重试次数 {retry_limit}，跳过下一个")

    try:
        for keyword in keywords:
            if task.cancelled:
                break
            await process_keyword(keyword)
            if not task.cancelled and get_effective_batch_step_delay_seconds() > 0:
                await asyncio.sleep(get_effective_batch_step_delay_seconds())
    except Exception as exc:
        logger.error(f"批量任务 {taskname} 执行失败: {exc}")
    finally:
        if taskname in request.app["tasks"]:
            task = request.app["tasks"][taskname]
            task.completed = True

            results_dir = "batch_results"
            os.makedirs(results_dir, exist_ok=True)
            result_file = os.path.join(results_dir, f"{taskname}_{int(datetime.now().timestamp())}.json")

            try:
                with open(result_file, "w", encoding="utf-8") as f:
                    result_data = {
                        "task_name": taskname,
                        "task_type": apptype,
                        "total_count": len(keywords),
                        "completed_count": task.curpro,
                        "query_keywords": task.query_keywords,
                        "result": task.domains,
                    }
                    json.dump(result_data, f, ensure_ascii=False, indent=2)

                db = request.app.get("db")
                if db:
                    success_count = sum(1 for item in task.domains if item is not None)
                    db.update_batch_task(
                        taskname,
                        completed_count=task.curpro,
                        success_count=success_count,
                        status="completed",
                        result_file=result_file,
                        finish_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    )
                    logger.info(f"批量任务 {taskname} 已完成，结果已保存到 {result_file}")
            except Exception as exc:
                logger.error(f"保存任务结果失败: {exc}")


@jsondump
@routes.view(r"/query/task")
async def querytask(request):
    taskname = request.query.get("taskname")
    task = request.app["tasks"].get(taskname)
    if task is None:
        return wj({"code": 404, "message": "任务不存在"})

    return wj({
        "code": 200,
        "curpro": task.curpro,
        "numpro": task.numpro,
        "tasktype": task.appname,
        "progress": int(task.curpro / task.numpro * 100) if task.numpro else 0,
        "query_keywords": task.query_keywords,
        "data": task.domains,
    })


@jsondump
@routes.view(r"/create/task")
async def create_task_catch(request):
    if request.method != "POST":
        return wj({"code": 405, "message": "Method not allowed"})

    data = await request.json()
    taskname = data.get("task")
    submitted_domains = data.get("data") or []
    seartype = data.get("type", "web")
    manual_proxy, proxy_error_message = parse_manual_proxy(data.get("proxy"))

    if proxy_error_message:
        return wj({"code": 400, "message": proxy_error_message})

    if seartype not in config.risk_avoidance.allow_type:
        return wj({"code": 405, "message": "不支持的查询类型"})

    submitted_count = len(submitted_domains)
    domains = []
    for item in submitted_domains:
        keyword = str(item or "").replace("\u3000", " ").strip()
        if keyword:
            domains.append(keyword)

    empty_filtered_count = submitted_count - len(domains)
    if len(domains) == 0:
        return wj({"code": 400, "message": "提交的查询列表为空"})

    risk_filtered_keywords = [s for s in domains if any(s.endswith(end) for end in config.risk_avoidance.prohibit_suffix)]
    domains = [s for s in domains if not any(s.endswith(end) for end in config.risk_avoidance.prohibit_suffix)]
    risk_filtered_count = len(risk_filtered_keywords)

    if len(domains) == 0:
        return wj({"code": 400, "message": "剔除不允许查询的内容后，列表为空，取消任务"})

    if taskname in request.app["tasks"]:
        return wj({"code": 409, "message": "任务已存在"})

    db = request.app.get("db")
    if db:
        db.add_batch_task(taskname, seartype, len(domains))

    task_coroutine = create_task(taskname, domains, request, seartype, manual_proxy)
    async_task = asyncio.create_task(task_coroutine)

    task_manager = request.app.get("task_manager")
    if task_manager:
        task_manager.add_task(taskname, async_task)

    batch_limit = get_batch_query_limit_config()
    logger.info(f"创建批量查询任务：{taskname}")
    log_collector.add_log(f"创建批量查询任务：{taskname}，类型：{seartype}，数量：{len(domains)}")
    return wj({
        "code": 200,
        "message": "任务已创建，批量查询将按配置的限速顺序执行",
        "data": {
            "submitted_count": submitted_count,
            "accepted_count": len(domains),
            "empty_filtered_count": empty_filtered_count,
            "risk_filtered_count": risk_filtered_count,
            "risk_filtered_keywords": risk_filtered_keywords[:20],
            "request_interval_ms": batch_limit.get("request_interval_ms", 6000),
            "max_per_minute": batch_limit.get("max_per_minute", 10),
            "window_seconds": batch_limit.get("window_seconds", 60),
            "effective_delay_seconds": get_effective_batch_step_delay_seconds(),
            "keyword_retry_limit": get_batch_keyword_retry_limit(),
            "keyword_retry_delay_min_seconds": get_batch_retry_delay_seconds(1),
            "keyword_retry_delay_max_seconds": get_batch_retry_delay_seconds(get_batch_keyword_retry_limit()),
        },
    })


@jsondump
@routes.view(r"/delete/task")
async def del_task(request):
    if request.method != "POST":
        return wj({"code": 405, "message": "Method not allowed"})

    data = await request.json()
    taskname = data.get("task")

    if taskname not in request.app["tasks"]:
        return wj({"code": 404, "message": "任务不存在，可能已经完成或删除"})

    task = request.app["tasks"][taskname]
    task.cancelled = True

    task_manager = request.app.get("task_manager")
    if task_manager:
        task_manager.remove_task(taskname)

    del request.app["tasks"][taskname]
    logger.warning(f"删除批量查询任务：{taskname}")
    log_collector.add_log(f"删除批量查询任务：{taskname}")
    return wj({"code": 200})


@routes.view(r"/batch/tasks")
async def get_batch_tasks(request):
    try:
        db = request.app.get("db")
        if not db:
            return wj({"code": 500, "message": "数据库未初始化"})

        limit = int(request.query.get("limit", 20))
        offset = int(request.query.get("offset", 0))
        status = request.query.get("status", "")

        tasks = db.get_batch_tasks(limit=limit, offset=offset, status=status if status else None)
        total = db.get_batch_tasks_count(status=status if status else None)
        return wj({"code": 200, "data": tasks, "total": total})
    except Exception as exc:
        logger.error(f"获取批量任务列表失败: {exc}")
        return wj({"code": 500, "message": f"获取任务列表失败: {str(exc)}"})


@routes.view(r"/batch/task/{task_name}")
async def get_batch_task_detail(request):
    try:
        task_name = request.match_info.get("task_name")
        db = request.app.get("db")
        if not db:
            return wj({"code": 500, "message": "数据库未初始化"})

        task = db.get_batch_task_detail(task_name)
        if not task:
            return wj({"code": 404, "message": "任务不存在"})

        if task.get("result_file") and os.path.exists(task["result_file"]):
            try:
                task["result_data"] = json.loads(read_text_guess(task["result_file"]))
            except Exception as exc:
                logger.error(f"读取结果文件失败: {exc}")

        return wj({"code": 200, "data": task})
    except Exception as exc:
        logger.error(f"获取批量任务详情失败: {exc}")
        return wj({"code": 500, "message": f"获取任务详情失败: {str(exc)}"})


@routes.view(r"/batch/task/delete/{task_name}")
async def delete_batch_task_api(request):
    try:
        task_name = request.match_info.get("task_name")
        db = request.app.get("db")
        if not db:
            return wj({"code": 500, "message": "数据库未初始化"})

        success = db.delete_batch_task(task_name)
        if success:
            return wj({"code": 200, "message": "删除成功"})
        return wj({"code": 500, "message": "删除失败"})
    except Exception as exc:
        logger.error(f"删除批量任务失败: {exc}")
        return wj({"code": 500, "message": f"删除任务失败: {str(exc)}"})


def setup_batch_routes(app):
    app.add_routes(routes)
