"""数据采集任务定时调度服务。

基于 APScheduler BackgroundScheduler，启动时从数据库全量加载 execute_type='02'
的定时任务，按 cron 表达式调度执行。任务变更时通过 add/remove 接口同步调度器。

cron 表达式兼容两种格式：
  - Quartz 6 字段：秒 分 时 日 月 周  （如 `0 0 2 * * ?`，每天凌晨2点）
  - Unix  5 字段：分 时 日 月 周      （如 `0 2 * * *`，每天凌晨2点）
其中 Quartz 的 `?` 会被替换为 `*`（APScheduler 不支持 `?` 语义）。
"""
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore

from app.core.db_collect import query_all_scheduled_tasks

_scheduler: BackgroundScheduler | None = None
_lock = threading.Lock()


def _parse_cron(cron_formula: str) -> CronTrigger:
    """解析 cron 表达式为 APScheduler CronTrigger。

    支持 Quartz 6 字段（含秒，`?` 替换为 `*`）和 Unix 5 字段。
    """
    expr = cron_formula.strip().replace("?", "*")
    parts = expr.split()
    if len(parts) == 6:
        # Quartz: 秒 分 时 日 月 周
        second, minute, hour, day, month, day_of_week = parts
        return CronTrigger(
            second=second, minute=minute, hour=hour,
            day=day, month=month, day_of_week=day_of_week,
        )
    elif len(parts) == 5:
        # Unix: 分 时 日 月 周
        minute, hour, day, month, day_of_week = parts
        return CronTrigger(
            second="0", minute=minute, hour=hour,
            day=day, month=month, day_of_week=day_of_week,
        )
    else:
        raise ValueError(
            f"cron 表达式字段数无效（应为 5 或 6 个字段，实际 {len(parts)} 个）: {cron_formula}"
        )


def _run_task(task_no: str):
    """调度器触发时的执行回调。延迟导入执行逻辑以避免循环导入。"""
    try:
        from app.api.routes.sample import execute_collect_task_internal
        result = execute_collect_task_internal(task_no, trigger_source="scheduler")
        print(f"[scheduler] 定时任务 {task_no} 执行完成: {result.get('message', '')}")
    except Exception as e:
        print(f"[scheduler] 定时任务 {task_no} 执行异常: {e}")


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        with _lock:
            if _scheduler is None:
                _scheduler = BackgroundScheduler(
                    jobstores={"default": MemoryJobStore()},
                    timezone="Asia/Shanghai",
                )
    return _scheduler


def init_scheduler():
    """初始化调度器并从数据库全量加载定时任务。应用启动时调用。"""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        print("[scheduler] 调度器已启动")

    # 全量加载定时任务
    try:
        tasks = query_all_scheduled_tasks()
        success_count = 0
        fail_count = 0
        for task in tasks:
            task_no = task["task_no"]
            cron_formula = task.get("cron_formula") or ""
            try:
                trigger = _parse_cron(cron_formula)
                scheduler.add_job(
                    _run_task,
                    trigger=trigger,
                    args=[task_no],
                    id=task_no,
                    replace_existing=True,
                    coalesce=True,
                    max_instances=1,
                )
                success_count += 1
            except Exception as e:
                fail_count += 1
                print(f"[scheduler] 加载定时任务 {task_no} 失败（cron={cron_formula}）: {e}")
        print(f"[scheduler] 定时任务加载完成：成功 {success_count} 个，失败 {fail_count} 个")
    except Exception as e:
        print(f"[scheduler] 加载定时任务异常: {e}")


def add_scheduled_task(task_no: str, cron_formula: str) -> bool:
    """新增或更新一个定时任务到调度器。返回是否成功。"""
    scheduler = get_scheduler()
    try:
        trigger = _parse_cron(cron_formula)
        scheduler.add_job(
            _run_task,
            trigger=trigger,
            args=[task_no],
            id=task_no,
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        print(f"[scheduler] 已添加定时任务 {task_no}（cron={cron_formula}）")
        return True
    except Exception as e:
        print(f"[scheduler] 添加定时任务 {task_no} 失败（cron={cron_formula}）: {e}")
        return False


def remove_scheduled_task(task_no: str):
    """从调度器移除一个定时任务。任务不存在时静默忽略。"""
    scheduler = get_scheduler()
    try:
        scheduler.remove_job(task_no)
        print(f"[scheduler] 已移除定时任务 {task_no}")
    except Exception:
        # 任务不存在等情况下静默忽略
        pass


def shutdown_scheduler():
    """关闭调度器。应用退出时调用。"""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        print("[scheduler] 调度器已关闭")
