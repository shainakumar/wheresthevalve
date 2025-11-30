from .hybrid_engine import HybridEngine
from .intent_rules import parse
from .router import build_query

UVA_TTL  = "brick/uva_schema.ttl"
INST_TTL = "graph/olsson_instances.ttl"
BRICK_TTL = None  # set to "brick/Brick.ttl" for full Brick  

def print_table(rows, cols):
    if not rows: print("(no results)"); return
    widths = [max(len(str(x)) for x in [c]+[r.get(c,"") for r in rows]) for c in cols]
    fmt = " | ".join(f"{{:{w}}}" for w in widths)
    print(fmt.format(*cols))
    print("-+-".join("-"*w for w in widths))
    for r in rows: print(fmt.format(*[str(r.get(c,"")) for c in cols]))

def main():
    eng = HybridEngine(UVA_TTL, INST_TTL, BRICK_TTL)

    print("Examples:")
    print("  leak in R2 sprinkler")
    print("  impacts of closing olsson:S7")
    print("(Enter to quit)\n")

    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text: break

        pr = parse(text)
        if pr.intent == "unknown":
            print(pr.missing.get("help","Try again.")); continue
        if pr.missing:
            print("I need: " + "; ".join(pr.missing.values())); continue

        _path, _q = build_query(pr)  # proves we’re using SPARQL templates

        if pr.intent == "leak_to_valves":
            room   = pr.slots.get("room")
            domain = pr.slots["domain"]
            specific = pr.slots.get("sprinkler")  # if you implemented Option A earlier

            if specific:
                # If the user named an exact head, keep the single-head path:
                res = eng.find_upstream_isolation(room, domain, target_valves=[specific])
                print("\nNearest isolation for the specified head:")
                print_table(res, ["hops","valve_id","label","room","domain","diameter_in","normally_open"])
                print()
            else:
                # ROOM query → show BOTH area-wide and per-head
                area, per_head = eng.find_upstream_isolation_both(room, domain, max_k_per_head=1)

                print("\nArea-wide recommended isolation valves (fewest hops from any head):")
                print_table(area, ["hops","valve_id","label","room","domain","diameter_in","normally_open"])

                print("\nPer-head nearest isolation (1 per head):")
                # Flatten per-head for a tidy table
                flat = []
                for h in per_head:
                    head = f"{h['head_label'] or h['head_id']}"
                    for iso in (h["nearest_isolations"] or []):
                        flat.append({
                            "head": head,
                            "iso_hops": iso["hops"],
                            "iso_valve_id": iso["valve_id"],
                            "iso_label": iso["label"],
                            "iso_room": iso["room"],
                        })
                if flat:
                    print_table(flat, ["head","iso_hops","iso_valve_id","iso_label","iso_room"])
                else:
                    print("(no per-head isolations found)")
                print()
        else:
            affected, rooms = eng.find_downstream_impacts(pr.slots["valve"])
            print("\nAffected valves (downstream):")
            print_table(affected, ["hops","valve_id","label","room","domain"])
            print("\nAffected rooms (by count):")
            print_table(rooms, ["count_affected_valves","label","room"])
            print()

if __name__ == "__main__":
    main()
