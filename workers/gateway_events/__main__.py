from __future__ import annotations

import argparse
import threading

from .analytics_writer import run as run_analytics_writer
from .enricher import run as run_enricher


def main() -> None:
    parser = argparse.ArgumentParser(description="Glimpse gateway event workers")
    parser.add_argument(
        "worker",
        choices=("enricher", "analytics-writer", "all"),
        help="Worker role to run",
    )
    args = parser.parse_args()

    if args.worker == "enricher":
        run_enricher()
        return

    if args.worker == "analytics-writer":
        run_analytics_writer()
        return

    threads = [
        threading.Thread(target=run_enricher, name="gateway-request-enricher"),
        threading.Thread(target=run_analytics_writer, name="gateway-analytics-writer"),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


if __name__ == "__main__":
    main()
