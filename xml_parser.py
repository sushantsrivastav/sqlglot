import re
import sys
import pandas as pd
import xml.etree.ElementTree as ET
from pathlib import Path

def strip_ns(elem):
    for e in elem.iter():
        if isinstance(e.tag, str) and "}" in e.tag:
            e.tag = e.tag.split("}", 1)[1]

def clean_source(expr: str) -> str:
    if not expr:
        return ""
    s = expr.strip()
    m = re.match(r"(?is)^\s*(nvl|coalesce)\s*\(\s*([^,]+?)\s*,.*\)\s*$", s)
    if m:
        s = m.group(2).strip()
    return s.strip().strip("'").strip('"')

def looks_like_ui_mapping(attr_name: str) -> bool:
    return bool(attr_name) and "ui_mapping_text" in attr_name.lower()

def xml_to_tabular(xml_path: str, out_xlsx: str = "ui_mappings.xlsx") -> None:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    strip_ns(root)

    rows = []
    diel_count = 0
    ui_hits = 0

    for diel in root.iter():
        if not (isinstance(diel.tag, str) and diel.tag.endswith("DIElement")):
            continue
        diel_count += 1

        target = (diel.get("name") or "").strip()
        if not target:
            continue

        # look for DIAttribute instead of DAttribute
        ui_attr = None
        for da in diel.findall(".//DIAttribute"):
            if looks_like_ui_mapping(da.get("name")):
                ui_attr = da
                break

        if ui_attr is None:
            continue

        ui_hits += 1
        raw_val = (ui_attr.get("value") or "").strip()
        if not raw_val or raw_val.lower() == "null":
            continue

        rows.append({
            "Target_Field": target,
            "Raw_ui_mapping_text": raw_val,
            "Parsed_Source": clean_source(raw_val),
        })

    if not rows:
        print(f"Found {diel_count} DIElement tags, but no usable DIAttribute ui_mapping_text values.")
        return

    df = pd.DataFrame(rows).sort_values("Target_Field").reset_index(drop=True)

    try:
        with pd.ExcelWriter(out_xlsx, engine="openpyxl") as xw:
            df.to_excel(xw, index=False, sheet_name="Mappings")
        print(f"Wrote {len(df)} mappings to {out_xlsx} (scanned {diel_count} DIElements; hits={ui_hits}).")
    except ModuleNotFoundError:
        csv_path = Path(out_xlsx).with_suffix(".csv")
        df.to_csv(csv_path, index=False)
        print(f"openpyxl not installed, wrote CSV instead: {csv_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python xml_to_tabular.py <input.xml> [output.xlsx]")
        sys.exit(1)

    xml_in = sys.argv[1]
    xlsx_out = sys.argv[2] if len(sys.argv) > 2 else "ui_mappings.xlsx"
    xml_to_tabular(xml_in, xlsx_out)
