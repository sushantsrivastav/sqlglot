#!/usr/bin/env python3
import re
import sys
import pandas as pd
import xml.etree.ElementTree as ET
from pathlib import Path

def strip_ns(elem):
    """Remove XML namespaces in-place so tags are plain names."""
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

def xml_to_excel(xml_path: str, out_xlsx: str = "ui_mappings.xlsx") -> None:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    strip_ns(root)

    rows = []
    dielements_seen = 0
    ui_attrs_seen = 0

    # Count all DIElements for sanity/debug
    for e in root.iter():
        if isinstance(e.tag, str) and e.tag.endswith("DIElement"):
            dielements_seen += 1

    # Iterate DIElements and look for DAttribute name="ui_mapping_text"
    for diel in root.iter():
        if not (isinstance(diel.tag, str) and diel.tag.endswith("DIElement")):
            continue

        target_name = (diel.get("name") or "").strip()
        if not target_name:
            continue

        # within this DIElement, look under DIAttibutes or DAttributes
        ui_attr = None
        for container in diel.findall("./DIAttibutes") + diel.findall("./DAttributes"):
            for da in container.findall("./DAttribute"):
                name_attr = (da.get("name") or "").strip().lower()
                if name_attr == "ui_mapping_text":
                    ui_attr = da
                    break
            if ui_attr:
                break

        # If not found via the containers, fall back to any descendant DAttribute
        if ui_attr is None:
            for da in diel.iter():
                if isinstance(da.tag, str) and da.tag.endswith("DAttribute"):
                    if (da.get("name") or "").strip().lower() == "ui_mapping_text":
                        ui_attr = da
                        break

        if ui_attr is None:
            continue

        ui_attrs_seen += 1
        raw_val = (ui_attr.get("value") or "").strip()
        if not raw_val or raw_val.lower() == "null":
            continue

        rows.append({
            "Target_Field": target_name,
            "Raw_ui_mapping_text": raw_val,
            "Parsed_Source": clean_source(raw_val),
        })

    if not rows:
        print(f"Found {dielements_seen} DIElement tags, but 0 usable ui_mapping_text values.")
        print("Tip: search the XML for 'ui_mapping_text' to confirm spelling/whitespace.")
        return

    df = pd.DataFrame(rows).sort_values("Target_Field").reset_index(drop=True)
    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name="Mappings")

    print(f"Wrote {len(df)} mappings to {out_xlsx} "
          f"(scanned {dielements_seen} DIElements; ui_mapping_text hits: {ui_attrs_seen}).")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        me = Path(sys.argv[0]).name
        print(f"Usage: {me} <input.xml> [output.xlsx]")
        sys.exit(1)
    xml_in = sys.argv[1]
    xlsx_out = sys.argv[2] if len(sys.argv) > 2 else "ui_mappings.xlsx"
    xml_to_excel(xml_in, xlsx_out)
