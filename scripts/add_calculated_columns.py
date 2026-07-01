"""Add calculated columns to a Parquet file."""

from pathlib import Path

from gen_parquet import add_calculated_columns

LOGIC_YAML_PATH = Path("/path/to/expression_logic.yaml")
PARQUET_PATH = Path("/path/to/input.parquet")
OUTPUT_PATH = Path("/path/to/output.calculated.parquet")


def main() -> None:
    output_path = add_calculated_columns(LOGIC_YAML_PATH, PARQUET_PATH, OUTPUT_PATH)
    print(output_path)


if __name__ == "__main__":
    main()
