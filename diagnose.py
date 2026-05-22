from __future__ import annotations

import importlib
import logging
import os
import tempfile
import sys
from pathlib import Path

from services.config_service import BASE_DIR, load_settings


MODULES = [
    "PySide6",
    "cv2",
    "torch",
    "ultralytics",
    "deepface",
]


def _configure_noisy_dependency_logs() -> None:
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    logging.getLogger("tensorflow").setLevel(logging.ERROR)


def _resolve_project_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return (BASE_DIR / candidate).resolve()


def _check_writable_directory(path: Path) -> tuple[bool, str]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=".diagnose_", dir=path, delete=True):
            pass
    except Exception as error:
        return False, str(error)
    return True, ""


def main() -> int:
    failed: list[tuple[str, str]] = []

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    _configure_noisy_dependency_logs()

    print("Проверка зависимостей:")
    for module_name in MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as error:
            failed.append((module_name, str(error)))
            print(f"[FAIL] {module_name}: {error}")
        else:
            print(f"[ OK ] {module_name}")

    print("\nПроверка настроек проекта:")
    try:
        settings = load_settings()
    except Exception as error:
        failed.append(("configs/settings.json", str(error)))
        print(f"[FAIL] configs/settings.json: {error}")
    else:
        print("[ OK ] configs/settings.json")

        model_path = _resolve_project_path(settings.models.face_detector_path)
        if model_path.exists():
            print(f"[ OK ] модель детекции лиц: {model_path}")
        else:
            message = f"файл не найден: {model_path}"
            failed.append(("face_detector_path", message))
            print(f"[FAIL] модель детекции лиц: {message}")

        for label, directory in (
            ("каталог журналов", _resolve_project_path(settings.logging.logs_dir)),
            ("каталог базы данных", _resolve_project_path(settings.database.path).parent),
        ):
            ok, message = _check_writable_directory(directory)
            if ok:
                print(f"[ OK ] {label}: {directory}")
            else:
                failed.append((label, message))
                print(f"[FAIL] {label}: {message}")

    if failed:
        print(f"\nПроблемы: {len(failed)}")
        return 1

    print("\nВсе ключевые зависимости, настройки и пути проекта проверены корректно.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
