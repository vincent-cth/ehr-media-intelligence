from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from time import perf_counter
from app.search import Embedder, SemanticIndex


def main() -> None:
    embedder = Embedder()
    index = SemanticIndex(embedder)
    rows=[]
    for i in range(50):
        rows.append({"record_id":str(i),"patient_id":f"P{i:04d}","patient_name":f"Synthetic {i}","resource_type":"DiagnosticReport" if i%2==0 else "DocumentReference","record_date":"2026-01-01","title":"Synthetic record","text":f"Synthetic clinical text record {i} with chest imaging and laboratory observations."})
    index.build(rows)
    start=perf_counter(); index.search("chest imaging laboratory", top_k=5); elapsed=perf_counter()-start
    print(f"50-record search latency: {elapsed:.4f}s")
    if elapsed >= 2.0:
        raise SystemExit("Latency target not met")

if __name__ == "__main__": main()
