from .hybrid_engine import HybridEngine

UVA_TTL   = "brick/uva_schema.ttl"
BRICK_TTL = None  # or "brick/Brick.ttl" if you want full Brick

SCENARIOS = {
    "case1": {
        "instances": "graph/testcase1.ttl",
        "description": "Split top/bottom in R2, leak on top branch (should pick Valve A)",
        "leak_node": "https://example.com/olsson#Top_R2",
        "room_iri":  "https://example.com/olsson#R2",
        "domain":    "https://uva.edu/schema#EmergencySprinkler",
        "valves_to_check_impacts": [
            "https://example.com/olsson#ValveA",
            "https://example.com/olsson#ValveB",
        ],
    },
    "case2": {
        "instances": "graph/testcase2.ttl",
        "description": "Two parallel pipes through one room; leak on top or bottom line",
        "leak_node": "https://example.com/olsson#Top_R1",   # leak on top pipe segment
        "room_iri":  "https://example.com/olsson#R1",
        "domain":    "https://uva.edu/schema#EmergencySprinkler",
        "valves_to_check_impacts": [
            "https://example.com/olsson#ValveA",
            "https://example.com/olsson#ValveB",
        ],
    },
    "case3": {
        "instances": "graph/testcase3.ttl",
        "description": "Looped pipe passes through the room twice; Fixture B also has a second independent feed",
        # Leak assumed on the loop return run near Fixture B
        "leak_node": "https://example.com/olsson#Loop_ReturnRun",
        "room_iri":  "https://example.com/olsson#L1",
        "domain":    "https://uva.edu/schema#EmergencySprinkler",
        "valves_to_check_impacts": [
            "https://example.com/olsson#VMain",
            "https://example.com/olsson#VLocal",
        ],
    },
}


def run_scenario(name: str, cfg: dict):
    print("=" * 70)
    print(f"SCENARIO: {name}")
    print(cfg["description"])
    print(f"Instances TTL: {cfg['instances']}")
    print(f"Leak node (seed): {cfg['leak_node']}")
    print("=" * 70)

    eng = HybridEngine(UVA_TTL, cfg["instances"], BRICK_TTL)

    # 1) Branch-specific leak: start from a specific segment/node
    upstream = eng.find_upstream_isolation_from_seeds(
        domain_iri=cfg["domain"],
        seed_ids=[cfg["leak_node"]],
    )

    print("\n[A] Branch-specific leak (single leak seed)")
    print("Upstream isolation candidates (fewest hops first):")
    if not upstream:
        print("  (none)")
    else:
        for r in upstream:
            print(
                f"  hops={r['hops']}, valve_id={r['valve_id']}, "
                f"label={r['label']}, room={r['room']}"
            )

    # 2) Room-wide leak: treat all pipe segments in the room as possible leak points
    print("\n[B] Room-level leak (pipe segment unknown)")
    segs, per_seg = eng.find_upstream_isolation_for_segments(
        room_iri=cfg["room_iri"],
        domain_iri=cfg["domain"],
    )

    if not segs:
        print("  No pipe segments found in this room for this domain.")
    else:
        print("\n  Per-segment nearest isolation valves:")
        for s in per_seg:
            seg_label = s["segment_label"]
            if not s["nearest_isolations"]:
                print(f"    {seg_label}: (no isolation valves found)")
                continue
            iso = s["nearest_isolations"][0]  # closest one
            print(
                f"    If leak on segment '{seg_label}', "
                f"close {iso['valve_id']} ({iso['label']}) "
                f"in room {iso['room']} (hops={iso['hops']})"
            )

    # 3) Downstream impacts for selected valves
    for vid in cfg["valves_to_check_impacts"]:
        print(f"\n[C] Downstream impacts of closing {vid}:")
        affected, rooms = eng.find_downstream_impacts(vid)

        print("  Affected valves/segments:")
        if not affected:
            print("    (none)")
        else:
            for a in affected:
                print(
                    f"    {a['valve_id']} ({a['label']}) "
                    f"in {a['room']}  hops={a['hops']}"
                )

        print("  Affected rooms (by count):")
        if not rooms:
            print("    (none)")
        else:
            for r in rooms:
                print(
                    f"    {r['room']}  valves={r['count_affected_valves']}"
                )


def main():
    for name, cfg in SCENARIOS.items():
        run_scenario(name, cfg)


if __name__ == "__main__":
    main()
