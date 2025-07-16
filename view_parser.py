import pandas as pd
import re
from sqlglot import parse_one, exp

def extract_select_sql(view_def: str) -> str:
    """Extract just the SELECT part from CREATE VIEW SQL."""
    match = re.search(r"\bAS\s+(SELECT.*)", view_def, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""

def resolve_aliases(ast):
    """
    Map table aliases to real table names.
    e.g., "SELECT s.id FROM sales s" -> {"s": "sales"}
    """
    alias_map = {}
    for from_expr in ast.find_all(exp.From):
        for source in from_expr.find_all(exp.TableAlias):
            alias = source.alias
            real_table = source.this
            if isinstance(real_table, exp.Table):
                alias_map[alias] = real_table.name
    return alias_map

def extract_column_lineage(ast, alias_map):
    lineage = []

    for select_expr in ast.expressions:
        if isinstance(select_expr, exp.Alias):
            col_expr = select_expr.this
            col_name = select_expr.alias_or_name
        else:
            col_expr = select_expr
            col_name = col_expr.sql()

        # Try to find the table (qualified identifier or alias)
        table_name = None
        if isinstance(col_expr, exp.Column):
            if col_expr.table:
                table_alias = col_expr.table
                table_name = alias_map.get(table_alias, table_alias)
            else:
                table_name = None  # could not resolve (e.g., derived column)

        lineage.append((col_name, table_name))

    return lineage

# Load the input CSV
df = pd.read_csv("view_definitions.csv")

output_rows = []

for _, row in df.iterrows():
    view_name = row["view_name"]
    view_def = row["view_definition"]
    select_sql = extract_select_sql(view_def)

    try:
        ast = parse_one(select_sql)
        alias_map = resolve_aliases(ast)
        lineage = extract_column_lineage(ast, alias_map)

        for col_name, table_name in lineage:
            output_rows.append({
                "view_name": view_name,
                "view_definition": select_sql,
                "table_name": table_name if table_name else "UNKNOWN",
                "column_name": col_name
            })

    except Exception as e:
        output_rows.append({
            "view_name": view_name,
            "view_definition": "ERROR",
            "table_name": "ERROR",
            "column_name": str(e)
        })

# Output to DataFrame and save
output_df = pd.DataFrame(output_rows)
output_df.to_csv("parsed_view_lineage.csv", index=False)
print("✅ Done. Output saved to parsed_view_lineage.csv")
