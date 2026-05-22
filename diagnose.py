from __future__ import annotations

import importlib
import sys


MODULES = [
    "PySide6",
    "cv2",
    "torch",
    "ultralytics",
    "deepface",
]


def main() -> int:
    failed: list[tuple[str, str]] = []

    for module_name in MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as error:
            failed.append((module_name, str(error)))
            print(f"[FAIL] {module_name}: {error}")
        else:
            print(f"[ OK ] {module_name}")

    if failed:
        print(f"\nПроблемы: {len(failed)}")
        return 1

    print("\nВсе ключевые зависимости импортируются корректно.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
