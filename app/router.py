from typing import Tuple
from intent_rules import ParseResult

TEMPLATES = {
    "leak_to_valves": ("queries/leak_to_valves.rq", ("__ROOM__","__DOMAIN__")),
    "impacts":        ("queries/impacts.rq",        ("__VALVE__",)),
}

def build_query(pr: ParseResult) -> Tuple[str,str]:
    if pr.intent not in TEMPLATES: raise ValueError("Unknown intent.")
    path, _ = TEMPLATES[pr.intent]
    q = open(path, "r", encoding="utf-8").read()
    if pr.intent == "leak_to_valves":
        if not {"room","domain"}.issubset(pr.slots): raise ValueError(f"Missing: {pr.missing}")
        q = q.replace("__ROOM__",   f"<{pr.slots['room']}>")
        q = q.replace("__DOMAIN__", f"<{pr.slots['domain']}>")
        return path, q
    if pr.intent == "impacts":
        if "valve" not in pr.slots: raise ValueError(f"Missing: {pr.missing}")
        q = q.replace("__VALVE__", f"<{pr.slots['valve']}>")
        return path, q
    raise ValueError("Unhandled intent.")
