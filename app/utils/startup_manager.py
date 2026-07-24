import ctypes
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import winreg
except ImportError:  # pragma: no cover - Windows-only feature.
    winreg = None

from app.config import APP_NAME, BASE_DIR, LOGS_DIR, RESOURCE_BASE_DIR


TASK_NAME = "ScheduleAppAutoStart"
LEGACY_APP_NAME = APP_NAME
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

_last_error_message = ""
_last_error_type = ""


def get_project_root() -> Path:
    """获取项目根目录。"""
    return RESOURCE_BASE_DIR if getattr(sys, "frozen", False) else BASE_DIR


def get_startup_manager_log_path() -> Path:
    return LOGS_DIR / "startup_manager.log"


def write_startup_manager_log(message: str) -> None:
    try:
        log_file = get_startup_manager_log_path()
        log_file.parent.mkdir(exist_ok=True)
        with log_file.open("a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception:
        pass


def is_running_as_admin() -> bool:
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def set_last_error(error_type: str = "", message: str = "") -> None:
    global _last_error_message, _last_error_type
    _last_error_type = error_type
    _last_error_message = message
    if error_type or message:
        write_startup_manager_log(f"last_error type={error_type}, message={message}")


def get_last_error_message() -> str:
    return _last_error_message


def get_last_error_type() -> str:
    return _last_error_type


def get_startup_action() -> tuple[Path, str, Path]:
    """
    返回任务计划程序动作需要的信息。

    program: 要运行的程序，例如 pythonw.exe 或打包后的 exe。
    arguments: 启动参数，例如 startup_launcher.pyw。
    working_dir: 预期工作目录；基础 schtasks 命令不直接写入，供展示和兼容使用。
    """
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable).resolve()
        return exe_path, "", exe_path.parent

    python_exe = Path(sys.executable).resolve()
    pythonw_exe = python_exe.with_name("pythonw.exe")
    launcher_python = pythonw_exe if pythonw_exe.exists() else python_exe

    project_root = get_project_root()
    launcher_path = project_root / "startup_launcher.pyw"

    return launcher_python, f'"{launcher_path}"', project_root


def get_startup_command() -> str:
    """获取启动程序路径或命令，仅用于展示或兼容。"""
    program, arguments, _ = get_startup_action()
    return f'"{program}" {arguments}'.strip()


def run_schtasks(args: list[str]) -> subprocess.CompletedProcess:
    write_startup_manager_log(
        "run_schtasks "
        f"admin={is_running_as_admin()}, sys.executable={sys.executable}, args={args}"
    )
    result = subprocess.run(
        ["schtasks", *args],
        capture_output=True,
        text=True,
        encoding="gbk",
        errors="ignore",
        shell=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    write_startup_manager_log(f"schtasks returncode={result.returncode}")
    write_startup_manager_log(f"schtasks stdout={result.stdout or ''}")
    write_startup_manager_log(f"schtasks stderr={result.stderr or ''}")
    return result


def is_access_denied_error(output: str) -> bool:
    output_lower = output.lower()
    return (
        "拒绝访问" in output
        or "拒絕訪問" in output
        or "access is denied" in output_lower
        or "access denied" in output_lower
    )


def is_task_not_found_output(output: str) -> bool:
    output_lower = output.lower()
    return (
        "找不到" in output
        or "无法找到" in output
        or "cannot find" in output_lower
        or "does not exist" in output_lower
        or "not found" in output_lower
    )


def cleanup_legacy_registry_startup() -> None:
    """删除旧版注册表 Run 中的 ScheduleApp 项，失败也不影响主流程。"""
    if winreg is None:
        return

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            try:
                winreg.DeleteValue(key, LEGACY_APP_NAME)
                write_startup_manager_log("legacy registry startup value removed")
            except FileNotFoundError:
                write_startup_manager_log("legacy registry startup value not found")
    except Exception as exc:
        write_startup_manager_log(f"legacy registry cleanup ignored: {exc}")


def create_scheduled_task() -> subprocess.CompletedProcess:
    task_run_command = get_startup_command()
    write_startup_manager_log(f"create_scheduled_task task_run_command={task_run_command}")
    return run_schtasks(
        [
            "/Create",
            "/TN",
            TASK_NAME,
            "/SC",
            "ONLOGON",
            "/TR",
            task_run_command,
            "/F",
        ]
    )


def delete_scheduled_task() -> subprocess.CompletedProcess:
    write_startup_manager_log("delete_scheduled_task")
    return run_schtasks(
        [
            "/Delete",
            "/TN",
            TASK_NAME,
            "/F",
        ]
    )


def enable_startup_without_elevation() -> bool:
    """普通权限尝试开启开机自启动。"""
    set_last_error()
    try:
        write_startup_manager_log("enable_startup_without_elevation started")
        result = create_scheduled_task()
        output = (result.stdout or "") + (result.stderr or "")

        if result.returncode == 0:
            cleanup_legacy_registry_startup()
            return True

        if is_access_denied_error(output):
            set_last_error("access_denied", "当前权限不足，需要管理员权限关闭开机自启动。")
        else:
            set_last_error("schtasks_failed", output.strip() or "创建任务计划程序任务失败。")
        return False
    except Exception as exc:
        set_last_error("schtasks_failed", f"创建任务计划程序任务异常：{exc}")
        return False


def disable_startup_without_elevation() -> bool:
    """普通权限尝试关闭开机自启动。"""
    set_last_error()
    try:
        write_startup_manager_log("disable_startup_without_elevation started")
        result = delete_scheduled_task()
        output = (result.stdout or "") + (result.stderr or "")

        cleanup_legacy_registry_startup()

        if result.returncode == 0 or is_task_not_found_output(output):
            return True

        if is_access_denied_error(output):
            set_last_error("access_denied", "当前权限不足，需要管理员权限完成开机自启动设置。")
        else:
            set_last_error("schtasks_failed", output.strip() or "删除任务计划程序任务失败。")
        return False
    except Exception as exc:
        set_last_error("schtasks_failed", f"删除任务计划程序任务异常：{exc}")
        return False


def get_elevated_helper_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return get_project_root() / "startup_elevated_helper.py"


def request_elevated_startup_change(action: str) -> bool:
    """通过 UAC 启动管理员辅助脚本。"""
    set_last_error()
    if action not in {"enable", "disable"}:
        set_last_error("elevation_failed", f"不支持的开机自启动操作：{action}")
        return False
    if os.name != "nt":
        set_last_error("elevation_failed", "当前系统不支持 Windows UAC 提权。")
        return False

    helper_path = get_elevated_helper_path()
    if not helper_path.exists():
        set_last_error("elevation_failed", f"管理员辅助脚本不存在：{helper_path}")
        return False

    program = str(Path(sys.executable).resolve())
    if getattr(sys, "frozen", False):
        params = f'--startup-elevated-helper {action}'
        working_dir = str(Path(sys.executable).resolve().parent)
    else:
        params = f'"{helper_path}" {action}'
        working_dir = str(helper_path.parent)

    write_startup_manager_log(
        "request_elevated_startup_change "
        f"action={action}, helper_path={helper_path}, program={program}, params={params}"
    )

    try:
        ret = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            program,
            params,
            working_dir,
            1,
        )
        write_startup_manager_log(f"ShellExecuteW return={ret}")
    except Exception as exc:
        set_last_error("elevation_failed", f"请求管理员权限失败：{exc}")
        return False

    if ret <= 32:
        set_last_error("elevation_cancelled", "用户取消了管理员权限授权。")
        return False

    return True


def wait_for_startup_state(expected_enabled: bool, timeout_seconds: int = 10) -> bool:
    """等待任务计划程序状态变为预期值。"""
    set_last_error()
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if is_startup_enabled() == expected_enabled:
            return True
        time.sleep(1)

    set_last_error("timeout", "等待管理员辅助脚本完成开机自启动设置超时。")
    return False


def enable_startup() -> bool:
    """开启开机自启动，优先使用普通权限创建任务计划程序任务。"""
    return enable_startup_without_elevation()


def disable_startup() -> bool:
    """关闭开机自启动，优先使用普通权限删除任务计划程序任务。"""
    return disable_startup_without_elevation()


def is_startup_enabled() -> bool:
    """检查任务计划程序中是否已经存在正确的自启动任务。"""
    try:
        result = run_schtasks(
            [
                "/Query",
                "/TN",
                TASK_NAME,
                "/V",
                "/FO",
                "LIST",
            ]
        )

        if result.returncode != 0:
            return False

        output = (result.stdout or "") + (result.stderr or "")
        program, _, _ = get_startup_action()

        if str(program) not in output:
            return False

        if not getattr(sys, "frozen", False):
            launcher_path = get_project_root() / "startup_launcher.pyw"
            if str(launcher_path) not in output:
                return False

        return True
    except Exception as exc:
        write_startup_manager_log(f"is_startup_enabled ignored exception: {exc}")
        return False
