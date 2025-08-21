#!/usr/bin/env python3
import re
import sys
import pandas as pd
import xml.etree.ElementTree as ET
from pathlib import Path

def strip_ns(elem):
    """Remove XML namespaces in-place so tag names are plain."""
    for e in elem.iter():
        if isinstance(e.tag, str) and "}" in e.tag:
            e.tag = e.tag.split("}", 1)[1]

def clean_source(expr: str) -> str:
    """Unwrap NVL/COALESCE and strip quotes."""
    if not expr:
        return ""
    s = expr.strip()
    m = re.match(r"(?is)^\s*(nvl|coalesce)\s*\(\s*([^,]+?)\s*,.*\)\s*$", s)
    if m:
        s = m.group(2).strip()
    return s.strip().strip("'").strip('"')

def looks_like_ui_mapping(attr_name: str) -> bool:
    """Match ui_mapping_text with tolerance to spaces/case/extra chars."""
    if not attr_name:
        return False
    n = attr_name.lower().strip()
    # tolerant: substring match covers 'ui_mapping_text ', 'UI_MAPPING_TEXT', etc.
    return "ui_mapping_text" in n

def xml_to_tabular(xml_path: str, out_xlsx: str = "ui_mappings.xlsx") -> None:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    strip_ns(root)

    rows = []
    dielements_seen = 0
    ui_attrs_seen = 0

    # Count DIElements
    for e in root.iter():
        if isinstance(e.tag, str) and e.tag.endswith("DIElement"):
            dielements_seen += 1

    # Iterate DIElements
    for diel in root.iter():
        if not (isinstance(diel.tag, str) and diel.tag.endswith("DIElement")):
            continue

        target_name = (diel.get("name") or "").strip()
        if not target_name:
            continue

        ui_attr = None

        # Try under DIAttibutes and DAttributes (both spellings)
        for container in diel.findall("./DIAttibutes") + diel.findall("./DAttributes"):
            for da in container.findall("./DAttribute"):
                if looks_like_ui_mapping(da.get("name")):
                    ui_attr = da
                    break
            if ui_attr:
                break

        # Fallback: any descendant DAttribute under this DIElement
        if ui_attr is None:
            for da in diel.iter():
                if isinstance(da.tag, str) and da.tag.endswith("DAttribute"):
                    if looks_like_ui_mapping(da.get("name")):
                        ui_attr = da
                        break

        if ui_attr is None:
            continue

        ui_attrs_seen += 1
        raw_val = (ui_attr.get("value") or "").strip()
        if not raw_val or raw_val.lower() == "null":
            # Skip empty/null mappings; remove this check if you want to include them
            continue

        rows.append({
            "Target_Field": target_name,              # e.g., ACCOUNT NUMBER
            "Raw_ui_mapping_text": raw_val,           # e.g., nvl(STG_LOAN_1.NOTE_NUMBER, 0)
            "Parsed_Source": clean_source(raw_val),   # e.g., STG_LOAN_1.NOTE_NUMBER
        })

    if not rows:
        print(f"Found {dielements_seen} DIElement tags, but 0 usable ui_mapping_text values.")
        print("Tip: open the XML and search for 'ui_mapping_text' to confirm spelling/whitespace.")
        return

    df = pd.DataFrame(rows).sort_values("Target_Field").reset_index(drop=True)

    # Write to Excel if possible, else CSV fallback
    try:
        with pd.ExcelWriter(out_xlsx, engine="openpyxl") as xw:
            df.to_excel(xw, index=False, sheet_name="Mappings")
        print(f"Wrote {len(df)} mappings to {out_xlsx} "
              f"(scanned {dielements_seen} DIElements; ui_mapping_text hits: {ui_attrs_seen}).")
    except ModuleNotFoundError:
        csv_path = Path(out_xlsx).with_suffix(".csv")
        df.to_csv(csv_path, index=False)
        print(f"openpyxl not found; wrote CSV instead: {csv_path} "
              f"(rows={len(df)}, DIElements={dielements_seen}, hits={ui_attrs_seen}).")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        me = Path(sys.argv[0]).name
        print(f"Usage: {me} <input.xml> [output.xlsx]")
        sys.exit(1)
    xml_in = sys.argv[1]
    xlsx_out = sys.argv[2] if len(sys.argv) > 2 else "ui_mappings.xlsx"
    xml_to_tabular(xml_in, xlsx_out)
