from __future__ import annotations

from app import write_dashboard_json


def main() -> None:
    target = write_dashboard_json()
    print(f"Wrote {target}")


if __name__ == "__main__":
    main()
