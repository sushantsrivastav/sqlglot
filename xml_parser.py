#!/usr/bin/env python3
import re
import sys
import pandas as pd
import xml.etree.ElementTree as ET
from pathlib import Path

# --- helpers ---------------------------------------------------------------

def strip_ns(elem):
    """Remove XML namespaces in-place so tag names are plain."""
    for e in elem.iter():
        if isinstance(e.tag, str) and "}" in e.tag:
            e.tag = e.tag.split("}", 1)[1]

def looks_like_ui_mapping(attr_name: str) -> bool:
    return bool(attr_name) and "ui_mapping_text" in attr_name.lower()

def remove_string_literals(expr: str) -> str:
    """Replace '...literal...' (single-quoted) with space to avoid false matches like 'yyyy.mm.dd'."""
    return re.sub(r"'[^']*'", " ", expr or "")

SRC_TOKEN_RE = re.compile(
    r"\b"                                 # word boundary
    r"[A-Za-z_][\w$]*"                    # part 1 (db or schema or table)
    r"\."                                 # dot
    r"[A-Za-z_][\w$]*"                    # part 2 (schema or table or column)
    r"(?:\.[A-Za-z_][\w$]*)?"             # optional part 3 (table or column)
)

def extract_sources(expr: str):
    """
    Return (primary_source, all_sources_list) by scanning for db.schema.table or table.column tokens.
    Prefers sources starting with 'STG_' as primary; otherwise first match.
    """
    if not expr:
        return "", []
    s = remove_string_literals(expr)
    matches = SRC_TOKEN_RE.findall(s)
    # de-duplicate while preserving order
    seen = []
    for m in matches:
        if m not in seen:
            seen.append(m)
    if not seen:
        return "", []
    primary = next((m for m in seen if m.upper().startswith("STG_")), seen[0])
    return primary, seen

# --- main ------------------------------------------------------------------

def xml_to_tabular(xml_path: str, out_xlsx: str = "ui_mappings.xlsx") -> None:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    strip_ns(root)

    rows = []
    diel_count = 0
    hits = 0

    for diel in root.iter():
        if not (isinstance(diel.tag, str) and diel.tag.endswith("DIElement")):
            continue
        diel_count += 1

        target = (diel.get("name") or "").strip()
        if not target:
            continue

        # DIAttribute (not DAttribute) under this DIElement
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

        primary, all_sources = extract_sources(raw)
        hits += 1
        rows.append({
            "Target_Field": target,
            "Raw_ui_mapping_text": raw,
            "Primary_Source": primary,                      # e.g., STG_LOAN_1.INTEREST_RATE
            "All_Sources": "; ".join(all_sources),          # e.g., STG_LOAN_1.X; DS_AFS.ETLAFS.Y
        })

    if not rows:
        print(f"Found {diel_count} DIElement tags, but no usable DIAttribute ui_mapping_text values.")
        return

    df = pd.DataFrame(rows).sort_values("Target_Field").reset_index(drop=True)

    # Prefer Excel; fall back to CSV if openpyxl isn't installed
    try:
        with pd.ExcelWriter(out_xlsx, engine="openpyxl") as xw:
            df.to_excel(xw, index=False, sheet_name="Mappings")
        print(f"Wrote {len(df)} mappings to {out_xlsx} (DIElements scanned={diel_count}, ui_mapping hits={hits}).")
    except ModuleNotFoundError:
        csv_path = Path(out_xlsx).with_suffix(".csv")
        df.to_csv(csv_path, index=False)
        print(f"openpyxl not installed; wrote CSV instead: {csv_path} (rows={len(df)}).")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python xml_to_mappings.py <input.xml> [output.xlsx]")
        sys.exit(1)
    xml_in = sys.argv[1]
    out_xlsx = sys.argv[2] if len(sys.argv) > 2 else "ui_mappings.xlsx"
    xml_to_tabular(xml_in, out_xlsx)
