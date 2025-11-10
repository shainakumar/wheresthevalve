import re
from dataclasses import dataclass
from typing import Dict, Optional

LEAK_WORDS   = ("leak","leaking","burst")
IMPACT_WORDS = ("impact","impacts","closing","close","shut","shutdown")
SPRINKLER_ID = re.compile(r"\bsprinkler\s+([A-Za-z][A-Za-z0-9_]+)\b", re.I)

DOMAIN_MAP = {
    "sprinkler": "https://uva.edu/schema#EmergencySprinkler",
    "emergency": "https://uva.edu/schema#EmergencySprinkler",
    "domestic":  "https://uva.edu/schema#Domestic",
    "potable":   "https://uva.edu/schema#Domestic",
}
BUILDING_PREFIX = "olsson:"

@dataclass
class ParseResult:
    intent: str
    slots: Dict[str,str]
    missing: Dict[str,str]

def _domain(text:str)->Optional[str]:
    tl = text.lower()
    for k,v in DOMAIN_MAP.items():
        if k in tl: return v
    m = re.search(r"https?://uva\.edu/schema#(Domestic|EmergencySprinkler)", text)
    return m.group(0) if m else None

def _room(text:str)->Optional[str]:
    m = re.search(r"\b([A-Za-z0-9_]+:[A-Za-z0-9_]+)\b", text)
    if m and m.group(1).lower().startswith(BUILDING_PREFIX): return m.group(1)
    m = re.search(r"\bR(\d+)\b", text, re.I)
    if m: return f"{BUILDING_PREFIX}R{m.group(1)}"
    m = re.search(r"\bzone\s*(\d+)\b", text, re.I)
    if m: return f"{BUILDING_PREFIX}R{m.group(1)}"
    return None

def _valve(text: str) -> Optional[str]:
    # 1) Full IRI already present, e.g., "olsson:MV1"
    m = re.search(r"\b([A-Za-z0-9_]+:[A-Za-z0-9_]+)\b", text)
    if m and m.group(1).lower().startswith("olsson:"):
        return m.group(1)

    # 2) Pattern: "olsson MV1" (namespace + next token)
    m = re.search(r"\bolsson\s+([A-Za-z][A-Za-z0-9_]+)\b", text, re.I)
    if m:
        return f"olsson:{m.group(1)}"

    # 3) Prefer valve-like tokens (S#, VG#, VH#, MV#, MainValve, V_Main, etc.)
    candidates = re.findall(r"\b([A-Za-z][A-Za-z0-9_]+)\b", text)
    PREFERRED = []
    for tok in candidates:
        t = tok.upper()
        if re.match(r"^S\d+$", t):             PREFERRED.append(tok)  # S7, S22...
        elif re.match(r"^VG\d+$", t):          PREFERRED.append(tok)  # VG1, VG2...
        elif re.match(r"^VH\d+$", t):          PREFERRED.append(tok)  # VH3...
        elif re.match(r"^MV\d+$", t):          PREFERRED.append(tok)  # MV1...
        elif t in {"MAINVALVE", "V_MAIN"}:     PREFERRED.append(tok)  # MainValve by label/alias

    if PREFERRED:
        # take the last matching token in the sentence (often the object of "closing")
        return f"olsson:{PREFERRED[-1]}"

    # 4) Fallback: last word token (less ideal, but better than the first)
    if candidates:
        return f"olsson:{candidates[-1]}"

    return None

def parse(text:str)->ParseResult:
    tl = text.lower()
    if any(w in tl for w in LEAK_WORDS):
        dom = _domain(text); rm = _room(text)
        missing = {}
        if not dom: missing["domain"] = "Add 'sprinkler' or 'domestic'."
        if not rm:  missing["room"]   = "Add a room/zone (e.g., 'R2' or 'zone 2')."
        slots = {}
        if dom: slots["domain"]=dom
        if rm:  slots["room"]=rm
       

        return ParseResult("leak_to_valves", slots, missing)

    if any(w in tl for w in IMPACT_WORDS):
        v = _valve(text)
        return ParseResult("impacts", {"valve": v} if v else {}, {} if v else {"valve":"Add a valve ID like 'S7'."})

    return ParseResult("unknown", {}, {"help":"Try 'leak in R2 sprinkler' or 'impacts of closing S7'."})

