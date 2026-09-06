from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.demo_corpus import build_raw_demo_records, write_demo_corpus


if __name__ == "__main__":
    json_path, csv_path = write_demo_corpus(ROOT / "data")
    json_records, csv_records = build_raw_demo_records()
    print(
        {
            "json_path": str(json_path.relative_to(ROOT)),
            "json_records": len(json_records),
            "csv_path": str(csv_path.relative_to(ROOT)),
            "csv_records": len(csv_records),
            "raw_records": len(json_records) + len(csv_records),
        }
    )
