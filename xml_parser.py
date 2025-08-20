#!/usr/bin/env python3
import re
import sys
import pandas as pd
import xml.etree.ElementTree as ET
from pathlib import Path

def clean_source(expr: str) -> str:
    """
    Return a cleaner source reference from common wrappers.
    e.g. "nvl(STG_LOAN_1.NOTE_NUMBER, 0)" -> "STG_LOAN_1.NOTE_NUMBER"
    """
    if not expr:
        return ""
    s = expr.strip()

    # Remove outer NVL(...) (case-insensitive)
    m = re.match(r'(?is)^\s*nvl\s*\(\s*([^,]+?)\s*,.*\)\s*$', s)
    if m:
        s = m.group(1).strip()

    # Remove surrounding quotes if any
    s = re.sub(r"^['\"]|['\"]$", "", s)
    return s

def xml_to_excel(xml_path: str, out_xlsx: str = "ui_mappings.xlsx") -> None:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    rows = []
    # Find every DIElement and look for its ui_mapping_text child attribute
    for diel in root.findall(".//DIElement"):
        target_name = diel.get("name") or ""
        if not target_name:
            continue

        attr = diel.find(".//DAttribute[@name='ui_mapping_text']")
        if attr is None:
            continue

        raw_val = (attr.get("value") or "").strip()
        if not raw_val or raw_val.lower() == "null":
            # skip empty / null mappings
            continue

        rows.append(
            {
                "Target_Field": target_name,                 # e.g., ACCOUNT_NUMBER
                "Raw_ui_mapping_text": raw_val,              # e.g., nvl(STG_LOAN_1.NOTE_NUMBER, 0)
                "Parsed_Source": clean_source(raw_val),      # e.g., STG_LOAN_1.NOTE_NUMBER
            }
        )

    if not rows:
        print("No ui_mapping_text entries found.")
        return

    df = pd.DataFrame(rows).sort_values(by=["Target_Field"]).reset_index(drop=True)

    # Nice, simple sheet
    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name="Mappings")

    print(f"Wrote {len(df)} mappings to {out_xlsx}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {Path(sys.argv[0]).name} <input.xml> [output.xlsx]")
        sys.exit(1)
    xml_in = sys.argv[1]
    xlsx_out = sys.argv[2] if len(sys.argv) > 2 else "ui_mappings.xlsx"
    xml_to_excel(xml_in, xlsx_out)
