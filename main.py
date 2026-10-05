"""Entry point: build the SQLite database (if needed) and run the RGM analysis.

Usage:
    python main.py            # build rgm.db on first run, then analyse
    python main.py --rebuild  # regenerate the data from scratch
"""

import argparse

import analysis
import generate_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Revenue Growth Management analyzer")
    parser.add_argument("--rebuild", action="store_true", help="regenerate rgm.db")
    args = parser.parse_args()

    if args.rebuild or not generate_data.DB_PATH.exists():
        generate_data.build()
        print(f"Database built: {generate_data.DB_PATH.name}")
    analysis.run(generate_data.DB_PATH)


if __name__ == "__main__":
    main()
