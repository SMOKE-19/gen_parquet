"""Command line interfaces for gen-parquet."""

from __future__ import annotations

import argparse
from pathlib import Path

from gen_parquet.core import (
    add_calculated_columns,
    package_name,
    txt_to_parquet,
    write_type_yamls_for_txt_dir,
)


def main() -> None:
    """Run the gen-parquet command."""
    print(f"{package_name()} is ready.")


def generate_type_yamls_main() -> None:
    """Generate type YAML files next to TSV text files in a directory."""
    parser = argparse.ArgumentParser(description="Generate type YAML files for TSV .txt files.")
    parser.add_argument("txt_dir", type=Path, help="Directory containing TSV .txt files.")
    parser.add_argument("--pattern", default="*.txt", help="Glob pattern to match input files.")
    parser.add_argument(
        "--sample-rows",
        type=int,
        default=None,
        help="Limit type inference to this many non-null values per column.",
    )
    parser.add_argument(
        "--comment-values",
        type=int,
        default=10,
        help="Number of sample values to write in YAML comments.",
    )
    args = parser.parse_args()

    yaml_paths = write_type_yamls_for_txt_dir(
        args.txt_dir,
        pattern=args.pattern,
        sample_rows=args.sample_rows,
        comment_values=args.comment_values,
    )
    for yaml_path in yaml_paths:
        print(yaml_path)


def convert_txt_to_parquet_main() -> None:
    """Convert one TSV text file to Parquet using a type YAML file."""
    parser = argparse.ArgumentParser(description="Convert a TSV .txt file to Parquet.")
    parser.add_argument("txt_path", type=Path, help="Input TSV .txt file.")
    parser.add_argument("type_yaml_path", type=Path, help="Type YAML file.")
    parser.add_argument("output_path", type=Path, help="Output Parquet file.")
    args = parser.parse_args()

    print(txt_to_parquet(args.txt_path, args.type_yaml_path, args.output_path))


def add_calculated_columns_main() -> None:
    """Add calculated columns to a Parquet file using expression YAML."""
    parser = argparse.ArgumentParser(description="Add calculated columns to a Parquet file.")
    parser.add_argument("logic_yaml_path", type=Path, help="Expression logic YAML file.")
    parser.add_argument("parquet_path", type=Path, help="Input Parquet file.")
    parser.add_argument("output_path", type=Path, help="Output Parquet file.")
    args = parser.parse_args()

    print(add_calculated_columns(args.logic_yaml_path, args.parquet_path, args.output_path))
