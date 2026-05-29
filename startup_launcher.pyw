import os
import runpy
import sys
import traceback
from datetime import datetime
from pathlib import Path


def write_startup_log(message: str) -> None:
    try:
        project_root = Path(__file__).resolve().parent
        log_dir = project_root / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "startup.log"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception:
        pass


def main() -> None:
    project_root = Path(__file__).resolve().parent
    main_py = project_root / "main.py"

    os.chdir(project_root)

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    write_startup_log("startup_launcher.pyw started")
    write_startup_log(f"about to run main.py: {main_py}")

    try:
        runpy.run_path(str(main_py), run_name="__main__")
    except SystemExit as exc:
        write_startup_log(f"main.py exited with code {exc.code}")
        raise
    except Exception:
        write_startup_log("main.py raised exception:")
        write_startup_log(traceback.format_exc())
        raise
    else:
        write_startup_log("main.py exited")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        write_startup_log("startup failed:")
        write_startup_log(traceback.format_exc())
