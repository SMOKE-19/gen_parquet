"""Convert a TSV .txt file to Parquet using a type YAML file."""

from pathlib import Path

from gen_parquet import txt_to_parquet

TXT_PATH = Path("/path/to/input.txt")
TYPE_YAML_PATH = Path("/path/to/input.yaml")
OUTPUT_PATH = Path("/path/to/output.parquet")
# 타입 샘플링은 YAML 생성 단계에서만 적용됩니다.
# 대용량 파일이라도 변환 단계는 YAML에 지정된 타입으로 전체 행을 Parquet로 씁니다.


def main() -> None:
    parquet_path = txt_to_parquet(TXT_PATH, TYPE_YAML_PATH, OUTPUT_PATH)
    print(parquet_path)


if __name__ == "__main__":
    main()
