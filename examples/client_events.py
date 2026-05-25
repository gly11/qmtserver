from __future__ import annotations

from qmtserver.client import QmtClient


def main() -> None:
    client = QmtClient("http://127.0.0.1:8000", token=None)
    for event in client.events():
        print(event)


if __name__ == "__main__":
    main()
