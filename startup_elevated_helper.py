import sys

from app.utils.startup_manager import (
    cleanup_legacy_registry_startup,
    create_scheduled_task,
    delete_scheduled_task,
    get_startup_command,
    is_task_not_found_output,
    is_running_as_admin,
    write_startup_manager_log,
)


def run_startup_helper_action(action: str) -> int:
    if action not in {"enable", "disable"}:
        write_startup_manager_log(
            f"startup_elevated_helper invalid action={action}, admin={is_running_as_admin()}"
        )
        return 2

    write_startup_manager_log(
        "startup_elevated_helper started "
        f"action={action}, admin={is_running_as_admin()}, sys.executable={sys.executable}"
    )
    write_startup_manager_log(f"startup_elevated_helper task_run_command={get_startup_command()}")

    if action == "enable":
        result = create_scheduled_task()
        if result.returncode == 0:
            cleanup_legacy_registry_startup()
            write_startup_manager_log("startup_elevated_helper enable succeeded")
            return 0
        write_startup_manager_log("startup_elevated_helper enable failed")
        return result.returncode or 1

    result = delete_scheduled_task()
    cleanup_legacy_registry_startup()
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode == 0 or is_task_not_found_output(output):
        write_startup_manager_log("startup_elevated_helper disable succeeded")
        return 0

    write_startup_manager_log("startup_elevated_helper disable failed")
    return result.returncode or 1


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"enable", "disable"}:
        write_startup_manager_log(
            f"startup_elevated_helper invalid args={sys.argv}, admin={is_running_as_admin()}"
        )
        return 2

    return run_startup_helper_action(sys.argv[1])


if __name__ == "__main__":
    sys.exit(main())
