"""Generate type suggestion YAML files next to TSV .txt files."""

from pathlib import Path

from gen_parquet import write_type_yamls_for_txt_dir

TXT_DIR = Path("/path/to/txt_dir")
# 기본값은 전체 행을 스캔해 타입을 제안합니다.
# 대용량 파일에서 일부 non-null 값만 보고 싶으면 아래처럼 sample_rows를 지정하세요.
# SAMPLE_ROWS = 1000
SAMPLE_ROWS = None


def main() -> None:
    yaml_paths = write_type_yamls_for_txt_dir(TXT_DIR, sample_rows=SAMPLE_ROWS)
    for yaml_path in yaml_paths:
        print(yaml_path)


if __name__ == "__main__":
    main()
