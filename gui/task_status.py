"""
任务状态集中定义与谓词。

存储值保持既有中文字符串，兼容旧 tasks_backup.json；
显示层的 ✅/❌ 前缀只由 display_text() 添加，绝不写入存储值。
worker 的进度文案存 info["progress_text"]，不允许覆盖 status。
"""

WAITING = "等待中"
CODE_MISSING = "番号待补充"
STARTED = "开始执行"
PREPARING = "准备中"
SCRAPING = "正在刮削..."
ORGANIZING = "整理中..."
SCRAPED = "已刮削(未整理)"
ORGANIZED = "已整理成功"
CANCELLED = "已取消"
FAILED_PREFIX = "失败: "

# 可重新发起任务的静止状态（过滤药丸「待整理」）
PENDING_STATES = (WAITING, SCRAPED, CODE_MISSING, CANCELLED)
# 有 worker 正在执行的状态
RUNNING_STATES = (STARTED, PREPARING, SCRAPING, ORGANIZING)


def failed(reason: str) -> str:
    return f"{FAILED_PREFIX}{reason}"


def is_running(status: str) -> bool:
    # 后两个模式兼容旧版备份里被进度文案覆盖过的 status
    return (status in RUNNING_STATES
            or status.startswith("正在")
            or status.endswith("中..."))


def is_failed(status: str) -> bool:
    # 子串匹配兼容旧版备份里的自由文本失败状态（如「整理异常: ...」）
    return (status.startswith(FAILED_PREFIX)
            or "失败" in status
            or "异常" in status)


def is_success(status: str) -> bool:
    return status == ORGANIZED


def display_text(status: str) -> str:
    """存储值 → 表格显示文案。前缀图标只存在于显示层。"""
    if is_success(status):
        return f"✅ {status}"
    if is_failed(status):
        return f"❌ {status}"
    return status
