from __future__ import annotations

from qmtserver.client import QmtClient


def main() -> None:
    client = QmtClient("http://127.0.0.1:8000", token=None)
    print(client.health())
    print(client.status())
    print(client.xtdata.get_full_tick(["000001.SZ"]))


if __name__ == "__main__":
    main()
