"""Read a stable historical prefix of the current experiment CSV."""
from pathlib import Path
from .csv_reader import CsvTail
from .normalize import normalize


def read_experiment_history(snapshot, metadata, data_root, duration_sec, after_seq, motor_id, model, identity):
    manifest = snapshot["experiment"]
    path = Path(manifest["csvPath"]).resolve()
    if not path.is_relative_to(Path(data_root).resolve()):
        raise ValueError("CSV path outside data root")
    latest = snapshot["latest"]
    through = latest["seq"] if latest else 0
    elapsed = latest["elapsedMs"] if latest else 0
    cutoff = max(0, elapsed - duration_sec * 1000) if duration_sec else 0
    samples = []
    reader = CsvTail(path)
    previous_elapsed = -1
    while through and reader.seq < through:
        records, replaced = reader.poll(manifest["status"] in {"completed", "interrupted", "failed"})
        if replaced or identity and reader.identity != identity:
            raise ValueError("CSV changed during history query")
        for seq, row, error in records:
            if seq > through:
                break
            if error:
                continue
            try:
                sample = normalize(row, manifest, metadata, seq,
                                   snapshot["serverSessionId"], snapshot["sourceSessionId"])
            except (ValueError, KeyError, TypeError):
                continue
            if sample["elapsedMs"] < previous_elapsed:
                continue
            previous_elapsed = sample["elapsedMs"]
            if seq > after_seq and sample["elapsedMs"] >= cutoff and (motor_id is None or sample["id"] == motor_id) and (not model or sample["model"] == model):
                samples.append(sample)
        if reader.eof:
            break
    if reader.seq < through:
        raise ValueError("CSV truncated during history query")
    return {"schemaVersion": 1, "runId": snapshot["runId"],
            "serverSessionId": snapshot["serverSessionId"], "sourceSessionId": snapshot["sourceSessionId"],
            "throughSeq": through, "latestElapsedMs": elapsed, "samples": samples}
