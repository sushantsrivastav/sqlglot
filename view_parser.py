import sqlglot
from sqlglot.expressions import Select, Column, Alias, Table, Create, Union, Subquery
import pandas as pd
import logging
import os

logging.getLogger("sqlglot").setLevel(logging.ERROR)

def get_full_table_name(table_expr: Table) -> str:
    """Get full qualified table name"""
    parts = []
    
    if isinstance(table_expr.args.get('db'), sqlglot.expressions.Dot):
        # Handle multi-part schema names
        dot_expr = table_expr.args['db']
        while isinstance(dot_expr, sqlglot.expressions.Dot):
            parts.insert(0, dot_expr.args['this'].name)
            dot_expr = dot_expr.args['expression']
        parts.append(dot_expr.name)
    elif table_expr.args.get('db'):
        parts.append(str(table_expr.args['db']))
    
    if table_expr.args.get('this'):
        parts.append(str(table_expr.args['this']))
    
    return '.'.join(parts)

def get_source_tables(select_stmt):
    """Get all source tables from a SELECT statement"""
    tables = {}
    
    # Process FROM clause
    from_clause = select_stmt.find(sqlglot.expressions.From)
    if from_clause:
        for table in from_clause.find_all(Table):
            full_name = get_full_table_name(table)
            alias = table.args.get('alias')
            if alias:
                tables[alias.name] = full_name
            else:
                tables[full_name.split('.')[-1]] = full_name

    # Process JOIN clauses
    for join in select_stmt.find_all(sqlglot.expressions.Join):
        if isinstance(join.this, Table):
            table = join.this
            full_name = get_full_table_name(table)
            alias = table.args.get('alias')
            if alias:
                tables[alias.name] = full_name
            else:
                tables[full_name.split('.')[-1]] = full_name

    return tables

def process_select_expression(expr, tables, default_table):
    """Process a single SELECT expression"""
    lineage = []
    
    # Get the view column name (target)
    view_col = expr.alias_or_name if isinstance(expr, Alias) else expr.sql()
    
    # Get the expression being assigned to the view column
    expr_inner = expr.this if isinstance(expr, Alias) else expr
    
    # Skip literals and NULL values
    if isinstance(expr_inner, (sqlglot.expressions.Literal, sqlglot.expressions.Null)):
        return lineage
    
    # Find all column references in the expression
    for col in expr_inner.find_all(Column):
        table_ref = col.table
        
        # Determine the source table
        if table_ref:
            source_table = tables.get(table_ref, table_ref)
        else:
            source_table = default_table
            
        lineage.append({
            "view_column": view_col,
            "source_column": col.name,
            "source_table": source_table
        })
    
    return lineage

def extract_column_lineage(sql_text: str) -> pd.DataFrame:
    """Extract column lineage from SQL view definition"""
    try:
        # Parse the SQL
        parsed = sqlglot.parse_one(sql_text)
        
        # Find the CREATE VIEW statement
        create_stmt = parsed.find(Create)
        if not create_stmt:
            return pd.DataFrame()
        
        all_lineage = []
        
        # Handle UNION ALL case
        union_stmt = create_stmt.find(Union)
        if union_stmt:
            for select in union_stmt.find_all(Select):
                # Get source tables for this SELECT
                tables = get_source_tables(select)
                default_table = next(iter(tables.values())) if tables else "UNKNOWN"
                
                # Process each expression in the SELECT
                for expr in select.expressions:
                    lineage = process_select_expression(expr, tables, default_table)
                    all_lineage.extend(lineage)
        else:
            # Handle single SELECT case
            select = create_stmt.find(Select)
            if select:
                tables = get_source_tables(select)
                default_table = next(iter(tables.values())) if tables else "UNKNOWN"
                
                for expr in select.expressions:
                    lineage = process_select_expression(expr, tables, default_table)
                    all_lineage.extend(lineage)
        
        # Create DataFrame
        df = pd.DataFrame(all_lineage)
        if not df.empty:
            # Clean up the results
            df = df[df['source_column'].notna()]
            df = df.drop_duplicates()
            
            # Handle cases where source_table is empty
            df['source_table'] = df['source_table'].fillna(df['source_table'].mode()[0])
            
            # Sort the results
            df = df.sort_values(['view_column', 'source_table', 'source_column'])
        
        return df
    
    except Exception as e:
        print(f"Error processing SQL: {str(e)}")
        return pd.DataFrame()

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Analyze SQL view definitions for column lineage')
    parser.add_argument('file_path', help='Path to the SQL file containing view definition')
    args = parser.parse_args()
    
    try:
        with open(args.file_path, "r") as f:
            sql = f.read()

        df = extract_column_lineage(sql)

        if df.empty:
            print("❌ No lineage found. Check if your SQL file has a valid SELECT block.")
        else:
            output_file = "lineage.csv"
            df.to_csv(output_file, index=False)
            print(f"✅ Lineage written to: {output_file}")
            print(df)
            
    except Exception as e:
        print(f"Error processing file: {str(e)}")

if __name__ == "__main__":
    main()
