from datetime import datetime
import math
import time


def normalize(row, manifest, metadata, seq, server_session, source_session):
    def number(key, integer=False, minimum=None, maximum=None):
        value = float(row[key])
        if not math.isfinite(value) or (integer and not value.is_integer()):
            raise ValueError(f"Invalid number: {key}")
        if minimum is not None and value < minimum or maximum is not None and value > maximum:
            raise ValueError(f"Out of range: {key}")
        return int(value) if integer else value

    model = row["Motor Model"]
    motor_id = number("Motor ID", True, 0, 252)
    if model != manifest["motorModel"] or motor_id != manifest["motorId"]:
        raise ValueError("CSV motor identity differs from manifest")
    raw = lambda key, bits=32: number(key, True, -(2 ** (bits - 1)), 2 ** (bits - 1) - 1)
    byte = lambda key: number(key, True, 0, 255)
    elapsed = number("Elapsed Time [s]", minimum=0) * 1000
    hw_error = byte("Hardware Error Status")
    moving = number("Moving", True, 0, 1)
    current = None
    load = None
    if model.startswith("XM430"):
        current = raw("Present Current", 16) * 0.00269
    elif model.startswith("XL430"):
        load = raw("Present Load", 16) * 0.1
    else:
        raise ValueError("Unsupported CSV motor model")
    timestamp = None
    try:
        stamp = datetime.fromisoformat(row["PC Time"])
        if stamp.tzinfo is None:
            zone = datetime.fromisoformat(metadata.get("created_at") or manifest["startedAt"]).tzinfo
            if zone is None:
                raise ValueError("Missing recording timezone")
            stamp = stamp.replace(tzinfo=zone)
        timestamp = stamp.timestamp() * 1000
    except (ValueError, TypeError, KeyError, OverflowError, OSError):
        pass
    goal = raw("Goal Position") if row.get("Goal Position", "") != "" else None
    return {
        "serverSessionId": server_session, "sourceSessionId": source_session,
        "runId": manifest["runId"], "busId": "experiment-csv", "seq": seq,
        "id": motor_id, "model": model, "status": "critical" if hw_error else "normal",
        "hwError": hw_error, "moving": bool(moving), "movingStatus": byte("Moving Status"),
        "realtimeTick": number("Realtime Tick", True, 0, 32767) if "Realtime Tick" in row else None,
        "pwm": raw("Present PWM", 16) * 0.113, "current": current, "loadPercent": load,
        "velocity": raw("Present Velocity") * 0.229, "position": raw("Present Position"),
        "velocityTrajectory": raw("Velocity Trajectory") * 0.229,
        "positionTrajectory": raw("Position Trajectory"), "goalPosition": goal,
        "goalSource": "command" if goal is not None else None,
        "voltage": number("Present Input Voltage", True, 0, 65535) * 0.1,
        "temperature": byte("Present Temperature"),
        "timestamp": timestamp, "pcTime": row["PC Time"], "elapsedMs": elapsed,
        "receivedAt": time.time() * 1000,
        "cycle": number("Cycle", True, 0) if row.get("Cycle") else None,
        "phase": row.get("Phase"), "condition": row.get("Condition"),
    }
