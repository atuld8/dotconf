#!/bin/bash

DB_NAME="$1"
TABLE_NAME="$2"  # Pass the table name as an argument

if [[ -z "$TABLE_NAME" ]] || [[ -z "$DB_NAME" ]]; then
    echo "Usage: $0 <db_name> <table_name>"
    exit 1
fi

echo "Finding dependencies for table: $TABLE_NAME"

# Query to find tables that depend on the given table
DEPENDENT_TABLES=$(psql --no-psqlrc -h localhost -p $PGPORT -U $PGUSER -d ${DB_NAME} -A -t -c "
SELECT conrelid::regclass
    FROM pg_constraint
    WHERE confrelid = '$TABLE_NAME'::regclass;" | awk '{$1=$1};1')

# Query to find tables that the given table depends on
REFERENCED_TABLES=$(psql --no-psqlrc -h localhost -p $PGPORT -U $PGUSER -d ${DB_NAME} -A -t -c "
SELECT confrelid::regclass
    FROM pg_constraint
    WHERE conrelid = '$TABLE_NAME'::regclass;" | awk '{$1=$1};1')

echo "-------- Tables that depend on $TABLE_NAME:"
echo "$DEPENDENT_TABLES"

echo ""
echo ""
echo ""
echo "-------- Tables that $TABLE_NAME depends on:"
echo "$REFERENCED_TABLES"

