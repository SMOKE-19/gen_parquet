"""Command line interface for gen-parquet."""

from gen_parquet.core import package_name


def main() -> None:
    """Run the gen-parquet command."""
    print(f"{package_name()} is ready.")
