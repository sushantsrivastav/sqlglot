#!/usr/bin/env python3
# xml_to_mappings_all_sources.py
import re
import sys
import pandas as pd
import xml.etree.ElementTree as ET
from pathlib import Path

# ---------- helpers ----------

def strip_ns(elem):
    """Remove XML namespaces in-place so tags are plain names."""
    for e in elem.iter():
        if isinstance(e.tag, str) and "}" in e.tag:
            e.tag = e.tag.split("}", 1)[1]

def looks_like_ui_mapping(attr_name: str) -> bool:
    """Match ui_mapping_text with tolerance to spaces/case."""
    return bool(attr_name) and "ui_mapping_text" in attr_name.lower()

def remove_string_literals(expr: str) -> str:
    """Replace single-quoted strings with spaces to avoid false matches."""
    return re.sub(r"'[^']*'", " ", expr or "")

# token: table.column  OR  schema.table.column (supports $, _ in names)
SRC_TOKEN_RE = re.compile(
    r"\b"                                 # word boundary
    r"[A-Za-z_][\w$]*"                    # part1 (db/schema/table)
    r"\."                                 # dot
    r"[A-Za-z_][\w$]*"                    # part2 (schema/table/column)
    r"(?:\.[A-Za-z_][\w$]*)?"             # optional part3 (table/column)
)

def extract_all_sources(expr: str):
    """Return a de-duplicated, order-preserved list of source tokens."""
    if not expr:
        return []
    s = remove_string_literals(expr)
    matches = SRC_TOKEN_RE.findall(s)
    seen = []
    for m in matches:
        if m not in seen:
            seen.append(m)
    return seen

# ---------- main ----------

def xml_to_tabular(xml_path: str, out_path: str = "ui_mappings.xlsx") -> None:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    strip_ns(root)

    rows = []
    diel_count = 0
    hit_count = 0

    # Iterate all DIElements
    for diel in root.iter():
        if not (isinstance(diel.tag, str) and diel.tag.endswith("DIElement")):
            continue
        diel_count += 1

        target = (diel.get("name") or "").strip()
        if not target:
            continue

        # Find the DIAttribute carrying ui_mapping_text under this DIElement
        ui_attr = None
        for da in diel.findall(".//DIAttribute"):
            if looks_like_ui_mapping(da.get("name")):
                ui_attr = da
                break
        if ui_attr is None:
            continue

        raw = (ui_attr.get("value") or "").strip()
        if not raw or raw.lower() == "null":
            continue

        sources = extract_all_sources(raw)
        hit_count += 1
        rows.append({
            "Target_Field": target,
            "Raw_ui_mapping_text": raw,
            "All_Sources": "; ".join(sources),  # keep as string for Excel
        })

    if not rows:
        print(f"Found {diel_count} DIElement tags, but no usable DIAttribute ui_mapping_text values.")
        return

    df = pd.DataFrame(rows).sort_values("Target_Field").reset_index(drop=True)

    # Write to Excel if possible; else CSV
    try:
        with pd.ExcelWriter(out_path, engine="openpyxl") as xw:
            df.to_excel(xw, index=False, sheet_name="Mappings")
        print(f"Wrote {len(df)} mappings to {out_path} "
              f"(DIElements scanned={diel_count}, ui_mapping hits={hit_count}).")
    except ModuleNotFoundError:
        csv_path = str(Path(out_path).with_suffix(".csv"))
        df.to_csv(csv_path, index=False)
        print(f"'openpyxl' not installed; wrote CSV instead: {csv_path} "
              f"(rows={len(df)}, DIElements={diel_count}, hits={hit_count}).")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        me = Path(sys.argv[0]).name
        print(f"Usage: {me} <input.xml> [output.xlsx]")
        sys.exit(1)
    xml_in = sys.argv[1]
    out_file = sys.argv[2] if len(sys.argv) > 2 else "ui_mappings.xlsx"
    xml_to_tabular(xml_in, out_file)
