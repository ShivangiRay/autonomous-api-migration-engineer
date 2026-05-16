from __future__ import annotations

import argparse

from libs.common.workflow import MigrationWorkflow


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("openapi_path")
    parser.add_argument("output_dir")
    args = parser.parse_args()
    result = MigrationWorkflow().run(args.openapi_path, args.output_dir)
    print(f"Generated migration report: {result['report_path']}")


if __name__ == "__main__":
    main()

