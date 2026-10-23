def choose_latest_complete(takes):
    if not takes:
        raise ValueError("Nessuna take candidata")
    complete = [take for take in takes if take.get("complete")]
    pool = complete or list(takes)
    selected = max(pool, key=lambda take: (take.get("take_index", 0), take.get("score", 0)))
    return {"selected": selected, "fallback": not bool(complete),
            "alternatives": [take for take in sorted(takes, key=lambda t: (t.get("take_index", 0), t.get("score", 0)), reverse=True)
                             if take is not selected]}
