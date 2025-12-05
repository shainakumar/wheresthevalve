from rdflib import Graph, URIRef, RDF, RDFS, Namespace
import networkx as nx
from collections import defaultdict, deque
from typing import Dict, List, Tuple
BRICK = Namespace("https://brickschema.org/schema/Brick#")
UVA   = Namespace("https://uva.edu/schema#")

class HybridEngine:

    # creating the rdf graph with schema and instance data 
    def __init__(self, uva_schema_ttl: str, instances_ttl: str, brick_ttl: str | None = None):
        self.g = Graph()
        if brick_ttl:
            self.g.parse(brick_ttl)
        self.g.parse(uva_schema_ttl)
        self.g.parse(instances_ttl)

        self.ns = {p: str(i) for p, i in self.g.namespaces()}
        self.ns.setdefault("brick", "https://brickschema.org/schema/Brick#")
        self.ns.setdefault("uva",   "https://uva.edu/schema#")

        self.RDFS_LABEL = URIRef("http://www.w3.org/2000/01/rdf-schema#label")
        self.BRICK_FEEDS = URIRef(self.ns["brick"] + "feeds")
        self.BRICK_HASLOC = URIRef(self.ns["brick"] + "hasLocation")

        self.nx = self._build_nx()

    # build the networkx directed graph from the rdf graph
    def _build_nx(self) -> nx.DiGraph:
        G = nx.DiGraph()
        RDF_T = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
        BRICK_Valve = URIRef(self.ns["brick"] + "Valve")
        hasDomain   = URIRef(self.ns["uva"]   + "hasDomain")
        hasDia      = URIRef(self.ns["uva"]   + "hasNominalDiameter")
        isNO        = URIRef(self.ns["uva"]   + "isNormallyOpen")

        # add all valves as nodes with attributes
        valves = set(s for (s, p, o) in self.g.triples((None, RDF_T, BRICK_Valve)))
        for v in valves:
            vid = str(v)
            label = next((str(o) for _s,_p,o in self.g.triples((v, self.RDFS_LABEL, None))), "")
            room  = next((str(o) for _s,_p,o in self.g.triples((v, self.BRICK_HASLOC, None))), "")
            dom   = next((str(o) for _s,_p,o in self.g.triples((v, hasDomain,   None))), "")
            dia   = next((str(o) for _s,_p,o in self.g.triples((v, hasDia,      None))), "")
            no    = next((str(o) for _s,_p,o in self.g.triples((v, isNO,        None))), "")
            G.add_node(vid, label=label, room=room, domain=dom,
                       diameter_in=dia, normally_open=no)

        # add any extra nodes that appear on feeds edges (pipe segments)
        for (s, _p, o) in self.g.triples((None, self.BRICK_FEEDS, None)):
            sid, oid = str(s), str(o)

            # ensure both endpoints exist as nodes
            if sid not in G:
                G.add_node(sid, label="", room="", domain="", diameter_in="", normally_open="")
            if oid not in G:
                G.add_node(oid, label="", room="", domain="", diameter_in="", normally_open="")

            # feeds relationships = edges 
            G.add_edge(sid, oid, domain=G.nodes[sid].get("domain", ""))

        return G

    # run a parameterized SPARQL query and return results
    def _run_query(self, rq_path: str, subs: Dict[str, str]):
        q = open(rq_path, "r", encoding="utf-8").read()
        for k, v in subs.items(): q = q.replace(k, v)
        return list(self.g.query(q))
    

    # standard BFS traversal (reverse=True for upstream)
    def _bfs(self, sources: List[str], reverse=False) -> Dict[str,int]:
        dist: Dict[str,int] = {}
        dq = deque()
        for s in sources:
            if s in self.nx:
                dist[s] = 0
                dq.append(s)
        neigh = (lambda u: self.nx.predecessors(u)) if reverse else (lambda u: self.nx.neighbors(u))
        while dq:
            u = dq.popleft()
            for v in neigh(u):
                if v not in dist:
                    dist[v] = dist[u] + 1
                    dq.append(v)
        return dist

    # find upstream isolation valves from a leak in a given room and domain
    def find_upstream_isolation(self, leak_room_iri: str, domain_iri: str) -> List[Dict]:
        # seeds = valves in the leak room with the same domain
        seeds = []
        for (v,_p,_o) in self.g.triples((None, self.BRICK_HASLOC, URIRef(leak_room_iri))):
            vid = str(v)
            if self.nx.nodes.get(vid,{}).get("domain")==domain_iri:
                seeds.append(vid)
        if not seeds: return []

        # candidates = all valves on this domain
        rows = self._run_query("queries/leak_to_valves.rq",
                               {"__ROOM__": f"<{leak_room_iri}>", "__DOMAIN__": f"<{domain_iri}>"})
        candidates = set(str(r[0]) for r in rows)

        dist = self._bfs(seeds, reverse=True)
        out = []
        # collect candidates found upstream 
        for vid in candidates:
            if vid in dist and dist[vid] > 0:
                a = self.nx.nodes[vid]
                # append valve info 
                out.append({
                    "hops": dist[vid],
                    "valve_id": vid,
                    "label": a.get("label",""),
                    "room": a.get("room",""),
                    "domain": a.get("domain",""),
                    "diameter_in": a.get("diameter_in",""),
                    "normally_open": a.get("normally_open",""),
                })
        # sort by hops + label 
        out.sort(key=lambda r: (r["hops"], r["label"]))
        return out

    # find downstream impacts of closing a given valve 
    def find_downstream_impacts(self, valve_iri: str) -> Tuple[List[Dict], List[Dict]]:
        rows = self._run_query("queries/impacts.rq", {"__VALVE__": f"<{valve_iri}>"})
        affected_ids = set(str(r[0]) for r in rows)
        dist = self._bfs([valve_iri], reverse=False)

        affected = []
        for vid in sorted(affected_ids, key=lambda x: (dist.get(x,10**9), x)):
            if vid == valve_iri: continue
            a = self.nx.nodes.get(vid, {})
            affected.append({
                "hops": dist.get(vid, -1),
                "valve_id": vid,
                "label": a.get("label",""),
                "room": a.get("room",""),
                "domain": a.get("domain",""),
            })
        # summarize impacts
        by_room = defaultdict(int); room_label = {}
        for rec in affected:
            rid = rec["room"]
            if not rid: continue
            by_room[rid] += 1
            lab = next((str(o) for _s,_p,o in self.g.triples((URIRef(rid), self.RDFS_LABEL, None))), rid)
            room_label[rid] = lab
        rooms = [{"room": rid, "label": room_label.get(rid,rid),
                  "count_affected_valves": cnt}
                 for rid, cnt in sorted(by_room.items(), key=lambda t: (-t[1], t[0]))]
        return affected, rooms
    
    # helper to get all valve/sprinkler seeds in a room for a domain
    def _room_domain_seeds(self, leak_room_iri: str, domain_iri: str) -> list[str]:
        seeds = []
        for (v, _, _) in self.g.triples((None, self.BRICK_HASLOC, URIRef(leak_room_iri))):
            vid = str(v)
            if self.nx.nodes.get(vid, {}).get("domain") == domain_iri:
                seeds.append(vid)
        return seeds
    
    # helper to get all pipe segments in a room for a domain
    def get_pipe_segments_in_room(self, room_iri: str, domain_iri: str):
        g = self.g
        room = URIRef(room_iri)
        domain = URIRef(domain_iri)

        segments = []

        for seg in g.subjects(RDF.type, UVA.PipeSegment):
            # check location
            loc = g.value(seg, BRICK.hasLocation)
            if loc != room:
                continue

            # check domain
            doms = list(g.objects(seg, UVA.hasDomain))
            if domain not in doms:
                continue

            label = g.value(seg, RDFS.label)
            segments.append({
                "seg_id": str(seg),
                "label": str(label) if label is not None else str(seg),
            })

        return segments
    
    # find upstream isolation valves starting from given seed IDs
    def find_upstream_isolation_from_seeds(self, domain_iri: str, seed_ids: List[str]):
        # only keep seeds that exist in the graph
        seeds = [s for s in seed_ids if s in self.nx]
        if not seeds:
            return []

        # candidates = all valves on this domain
        candidates = [
            vid for vid, attrs in self.nx.nodes(data=True)
            if attrs.get("domain") == domain_iri
        ]

        # upstream BFS from the seeds
        dist = self._bfs(seeds, reverse=True)

        out = []
        for vid in candidates:
            if vid in dist and dist[vid] > 0:
                a = self.nx.nodes[vid]
                out.append({
                    "hops": dist[vid],
                    "valve_id": vid,
                    "label": a.get("label", ""),
                    "room": a.get("room", ""),
                    "domain": a.get("domain", ""),
                    "diameter_in": a.get("diameter_in", ""),
                    "normally_open": a.get("normally_open", ""),
                })

        out.sort(key=lambda r: (r["hops"], r["label"]))
        return out
    
    # find upstream isolation valves for each pipe segment in a room
    def find_upstream_isolation_for_segments(self, room_iri: str, domain_iri: str):
        segments = self.get_pipe_segments_in_room(room_iri, domain_iri)
        if not segments:
            return [], []

        per_segment = []

        for seg in segments:
            sid = seg["seg_id"]
            label = seg["label"]

            iso_list = self.find_upstream_isolation_from_seeds(
                domain_iri=domain_iri,
                seed_ids=[sid],
            )

            per_segment.append({
                "segment_id": sid,
                "segment_label": label,
                "nearest_isolations": iso_list,
            })

        return segments, per_segment

    # find both area-wide (for whole room- same logic as find_upstream_isolation()) and per-head upstream isolations
    def find_upstream_isolation_both(self, leak_room_iri: str, domain_iri: str, max_k_per_head: int = 1):
        seeds = self._room_domain_seeds(leak_room_iri, domain_iri)
        if not seeds:
            return [], []

        # all upstream candidates on the correct domain
        rows = self._run_query(
            "queries/leak_to_valves.rq",
            {"__ROOM__": f"<{leak_room_iri}>", "__DOMAIN__": f"<{domain_iri}>"}
        )
        candidates = set(str(r[0]) for r in rows)  # ?valve IRIs

        # area-wide: multi-source upstream BFS (fewest hops from ANY seed)
        dist_multi = self._bfs(seeds, reverse=True)
        area_wide = []
        for vid in candidates:
            if vid in dist_multi and dist_multi[vid] > 0:  
                a = self.nx.nodes[vid]
                area_wide.append({
                    "hops": dist_multi[vid],
                    "valve_id": vid,
                    "label": a.get("label", ""),
                    "room": a.get("room", ""),
                    "domain": a.get("domain", ""),
                    "diameter_in": a.get("diameter_in", ""),
                    "normally_open": a.get("normally_open", ""),
                })
        area_wide.sort(key=lambda r: (r["hops"], r["label"]))

        # per-head: run single-source BFS for each seed and pick nearest candidate(s)
        per_head = []
        for seed in seeds:
            dist_seed = self._bfs([seed], reverse=True)
            choices = []
            for vid in candidates:
                if vid in dist_seed and dist_seed[vid] > 0:
                    a = self.nx.nodes[vid]
                    choices.append({
                        "hops": dist_seed[vid],
                        "valve_id": vid,
                        "label": a.get("label", ""),
                        "room": a.get("room", ""),
                        "domain": a.get("domain", ""),
                        "diameter_in": a.get("diameter_in", ""),
                        "normally_open": a.get("normally_open", ""),
                    })
            choices.sort(key=lambda r: (r["hops"], r["label"]))
            # metadata about the head itself
            head_label = self.nx.nodes[seed].get("label", "")
            head_room  = self.nx.nodes[seed].get("room", "")
            per_head.append({
                "head_id": seed,
                "head_label": head_label,
                "head_room": head_room,
                "nearest_isolations": choices[:max_k_per_head] if max_k_per_head else choices
            })

        return area_wide, per_head
