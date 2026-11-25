#!/usr/bin/env python3
"""
srg2mojmap.py - rewrite SRG identifiers (m_12345_ / f_12345_) in Java sources to Mojang names.

The decompiled 1.19.2 sources are full of SRG names because Forge reobfuscates mods to SRG.
Your 1.20.1 workspace compiles against official Mojang names, so every one of them must be renamed.
This tool does the rename exactly (no guessing) by joining two files published for the SAME
Minecraft version (use 1.19.2 here - the identifiers come from the 1.19.2 jar):

  1. Mojang's official mappings        (client.txt, from the version JSON "downloads.client_mappings")
                                       (server.txt too, optional: pass --mojang twice)
  2. MCPConfig's joined.tsrg           (obf -> SRG; inside the zip
                                       de.oceanlabs.mcp:mcp_config:1.19.2-20220805.130853 -> config/joined.tsrg)

Usage:
  python srg2mojmap.py --mojang client.txt --tsrg joined.tsrg  SRC_DIR  OUT_DIR
  python srg2mojmap.py --mojang client.txt --tsrg joined.tsrg --dump-map map.csv   (just export the table)

Files written to OUT_DIR keep the same layout. unmapped_ids.txt lists SRG ids that had no match.
"""
import argparse, csv, os, re, sys

PRIM = {"byte": "B", "char": "C", "double": "D", "float": "F", "int": "I", "long": "J",
        "short": "S", "boolean": "Z", "void": "V"}
SRG_RE = re.compile(r"\b([mf])_(\d+)_\b")


def parse_mojang(paths):
    """returns (classes: {mojang_dotted: obf_dotted}, members: list of (kind, mojang_cls, name, mojang_sig, obf))"""
    classes, raw = {}, []
    for path in paths:
        cur = None
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line or line.startswith("#"):
                    continue
                if not line.startswith(" "):
                    m = re.match(r"(\S+) -> (\S+):$", line)
                    if m:
                        cur = m.group(1)
                        classes[cur] = m.group(2)
                    continue
                body = line.strip()
                m = re.match(r"(?:\d+:\d+:)?(\S+) ([^\s(]+)\((.*)\) -> (\S+)$", body)
                if m:
                    raw.append(("m", cur, m.group(2), (m.group(1), m.group(3)), m.group(4)))
                    continue
                m = re.match(r"(\S+) (\S+) -> (\S+)$", body)
                if m:
                    raw.append(("f", cur, m.group(2), m.group(1), m.group(3)))
    return classes, raw


def to_desc(java_type, classes):
    dims = 0
    while java_type.endswith("[]"):
        dims += 1
        java_type = java_type[:-2]
    if java_type in PRIM:
        d = PRIM[java_type]
    else:
        d = "L" + classes.get(java_type, java_type).replace(".", "/") + ";"
    return "[" * dims + d


def parse_tsrg(path):
    """returns {(obf_cls, obf_name, desc_or_None): srg_id} and {obf_cls: mapped_name}"""
    table, cls_map, cur = {}, {}, None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("tsrg2"):
                continue
            if not line.startswith("\t"):
                tok = line.split()
                cur = tok[0]
                cls_map[cur] = tok[1] if len(tok) > 1 else tok[0]
                continue
            if line.startswith("\t\t"):
                continue  # parameters / static markers (tsrg2)
            tok = line.split()
            if len(tok) >= 3 and tok[1].startswith("("):
                srg = next((t for t in tok[2:] if re.fullmatch(r"m_\d+_", t)), None)
                if srg:
                    table[(cur, tok[0], tok[1])] = srg
            else:
                srg = next((t for t in tok[1:] if re.fullmatch(r"f_\d+_", t)), None)
                if srg:
                    table[(cur, tok[0], None)] = srg
    return table, cls_map


def build_map(mojang_paths, tsrg_path):
    classes, raw = parse_mojang(mojang_paths)
    table, _ = parse_tsrg(tsrg_path)
    out = {}
    for kind, mcls, name, sig, obf in raw:
        ocls = classes.get(mcls)
        if ocls is None:
            continue
        ocls = ocls.replace(".", "/")
        if kind == "f":
            srg = table.get((ocls, obf, None))
        else:
            ret, args = sig
            desc = "(" + "".join(to_desc(a.strip(), classes) for a in args.split(",") if a.strip()) + ")" + to_desc(ret, classes)
            srg = table.get((ocls, obf, desc))
        if srg:
            out.setdefault(srg, name)
    return out


def rewrite(text, mapping, missing):
    def sub(m):
        key = m.group(0)
        if key in mapping:
            return mapping[key]
        missing.add(key)
        return key
    return SRG_RE.sub(sub, text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mojang", action="append", required=True, help="Mojang mappings file (repeatable)")
    ap.add_argument("--tsrg", required=True, help="MCPConfig joined.tsrg")
    ap.add_argument("--dump-map", help="write the srg->mojang table as CSV and exit")
    ap.add_argument("src", nargs="?")
    ap.add_argument("out", nargs="?")
    a = ap.parse_args()

    mapping = build_map(a.mojang, a.tsrg)
    print(f"mapping table: {len(mapping)} entries", file=sys.stderr)
    if a.dump_map:
        with open(a.dump_map, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["srg", "mojang"])
            for k in sorted(mapping):
                w.writerow([k, mapping[k]])
        return
    if not (a.src and a.out):
        ap.error("src and out directories are required")

    missing, n = set(), 0
    for root, _, files in os.walk(a.src):
        for f in files:
            if not f.endswith(".java"):
                continue
            p = os.path.join(root, f)
            dst = os.path.join(a.out, os.path.relpath(p, a.src))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(p, encoding="utf-8") as fh:
                txt = fh.read()
            with open(dst, "w", encoding="utf-8") as fh:
                fh.write(rewrite(txt, mapping, missing))
            n += 1
    with open(os.path.join(a.out, "unmapped_ids.txt"), "w") as fh:
        fh.write("\n".join(sorted(missing)) + ("\n" if missing else ""))
    print(f"rewrote {n} files; {len(missing)} ids had no mapping (see unmapped_ids.txt)", file=sys.stderr)


if __name__ == "__main__":
    main()
