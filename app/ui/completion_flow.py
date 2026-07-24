from PySide6.QtWidgets import QMessageBox

from app.services.period_service import period_service
from app.ui.completion_dialog import CompletionDialog


def prompt_and_complete_task(parent, task_service, task_id):
    task = task_service.get_task_by_id(task_id)
    if task is None:
        QMessageBox.warning(parent, "提示", "对应任务不存在")
        return False
    if task.is_completed:
        QMessageBox.warning(parent, "提示", "任务已经完成")
        return False

    dialog = CompletionDialog(task.title, parent)
    if not dialog.exec():
        return False

    try:
        task_service.complete_task(task_id, dialog.completion_note())
    except ValueError as error:
        QMessageBox.warning(parent, "提示", str(error))
        return False
    except Exception as error:
        QMessageBox.warning(parent, "提示", f"数据库写入失败：{error}")
        return False
    return True


def prompt_and_complete_daily_checkin(parent, task_service, daily_task_id, target_date=None):
    task = task_service.get_task_by_id(daily_task_id)
    if task is None:
        QMessageBox.warning(parent, "提示", "对应任务不存在")
        return False

    target_date = period_service.normalize_date(target_date)
    dialog = CompletionDialog(task.title, parent)
    if not dialog.exec():
        return False

    try:
        task_service.set_daily_checkin_with_plan_sync(
            daily_task_id,
            target_date,
            True,
            completion_note=dialog.completion_note(),
        )
    except ValueError as error:
        QMessageBox.warning(parent, "提示", str(error))
        return False
    except Exception as error:
        QMessageBox.warning(parent, "提示", f"数据库写入失败：{error}")
        return False
    return True
