#!/usr/bin/awk -f
#
# remove_col.awk
#
# Remove one or more columns from ASCII tables (| and + separators)
# while preserving formatting and alignment.
#
# Supported features:
# - Tables using '|' for columns and '+' for separators
# - Variable column widths
# - Remove multiple columns in one run
# - Remove columns by header name (not index)
# - Correct handling of the first separator line
#
# Usage:
#   awk -v remove="COL1,COL2" -f remove_col.awk input.txt
#
# Examples:
#
#   Remove a single column:
#     awk -v remove="Sr." -f remove_col.awk table.txt
#
#   Remove multiple columns:
#     awk -v remove="Sr.,Severity" -f remove_col.awk table.txt
#
#   Remove columns from piped input:
#     cat table.txt | awk -v remove="Reporter,CVSS" -f remove_col.awk
#
# Notes:
# - Column names must exactly match the header text (case-sensitive)
# - Whitespace around column names is ignored
# - Column order is preserved
# - Works well with Jira, SQL, and CLI-generated tables
#

BEGIN {
    FS="|"
    OFS="|"

    if (remove == "") {
        print "ERROR: No columns specified."
        print "Usage: awk -v remove=\"COL1,COL2\" -f remove_col.awk file"
        exit 1
    }
    # Columns to remove (comma-separated header names)
    # Example usage:
    # awk -v remove="Sr.,Severity" -f remove_col.awk file.txt
    split(remove, r, ",")
    for (i in r) {
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", r[i])
        remove_name[r[i]] = 1
    }

    header_done = 0
    first_sep = ""
    printed_first_sep = 0
}

# Separator line ( +-----+-----+ )
/^[[:space:]]*\+/ {
    if (!header_done && first_sep == "") {
        first_sep = $0
        next
    }

    split($0, parts, "+")
    out = "+"
    for (i = 2; i < length(parts); i++) {
        if (!(i in drop_col)) {
            out = out parts[i] "+"
        }
    }
    print out
    next
}

# Header row
/^\|/ && !header_done {
    for (i = 2; i <= NF - 1; i++) {
        col = $i
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", col)
        if (col in remove_name) {
            drop_col[i] = 1
        }
    }

    # Print reconstructed first separator now that columns are known
    if (first_sep != "" && !printed_first_sep) {
        split(first_sep, parts, "+")
        out = "+"
        for (i = 2; i < length(parts); i++) {
            if (!(i in drop_col)) {
                out = out parts[i] "+"
            }
        }
        print out
        printed_first_sep = 1
    }

    # Print header row
    out = "|"
    for (i = 2; i <= NF - 1; i++) {
        if (!(i in drop_col)) {
            out = out $i "|"
        }
    }
    print out

    header_done = 1
    next
}

# Data rows
/^\|/ {
    out = "|"
    for (i = 2; i <= NF - 1; i++) {
        if (!(i in drop_col)) {
            out = out $i "|"
        }
    }
    print out
    next
}

# Anything else
{
    print
}

