BEGIN {
    # Default column widths
    ColumnWidth["ABSTRACT"]=60
    ColumnWidth["CATEGORY"]=20
    ColumnWidth["CHANGED_BY"]=20
    ColumnWidth["COMPONENT"]=30
    ColumnWidth["DATE_CLOSED"]=11
    ColumnWidth["DATE_FIXED"]=11
    ColumnWidth["DATE_OPENED"]=14
    ColumnWidth["DEFAULT"]=12
    ColumnWidth["INCIDENT"]=8
    ColumnWidth["KEYWORD"]=20
    ColumnWidth["LAST_CHANGED"]=11
    ColumnWidth["PLATFORM"]=13
    ColumnWidth["PRIORITY"]=3
    ColumnWidth["PRODUCT"]=10
    ColumnWidth["PROGRESS_STATUS"]=40
    ColumnWidth["REPORTER"]=20
    ColumnWidth["SEVERITY"]=3
    ColumnWidth["STATE"]=10
    ColumnWidth["SUBSCRIBE"]=40
    ColumnWidth["TYPE"]=17
    ColumnWidth["TARGET_BUILD"]=13
    ColumnWidth["TARGET_VERSION"]=10
    ColumnWidth["USER_DEFINED"]=20
    ColumnWidth["USER_DEFINED2"]=30
    ColumnWidth["VERSION"]=8
    
    # Serial number column width
    SRNO_WIDTH = 5
    row_num = 0
    header_done = 0
    data_rows = 0
    
    # Custom widths storage (user overrides)
    # These are parsed from cols or headers with :WIDTH suffix
    
    # Parse cols with optional :WIDTH format
    # e.g., cols=INCIDENT:20,STATE:30,ABSTRACT
    Columns = split(cols, rawCols, ",")
    for (i = 1; i <= Columns; i++) {
        # Check if column has :WIDTH suffix using split
        colonPos = index(rawCols[i], ":")
        if (colonPos > 0) {
            colName = substr(rawCols[i], 1, colonPos - 1)
            widthStr = substr(rawCols[i], colonPos + 1)
            customWidth = int(widthStr)
            if (customWidth > 0) {
                CustomWidth[colName] = customWidth
            }
            out[i] = colName
        } else {
            out[i] = rawCols[i]
        }
    }
    
    # Parse headers (column names only, no width support)
    # e.g., headers=INCIDENT,STATE,ABSTRACT
    if (headers != "") {
        HeaderCount = split(headers, rawHeaders, ",")
        for (i = 1; i <= HeaderCount; i++) {
            HeaderNames[i] = rawHeaders[i]
        }
    }
    
    # Check for help flag
    if (help == 1) {
        print_usage()
        exit 0
    }
}

# Function to print usage information
function print_usage() {
    print ""
    print "USAGE:"
    print "  awk -F \"\\t\" -f et_data_in_col.awk [OPTIONS] < input_file"
    print "  command | awk -F \"\\t\" -f et_data_in_col.awk [OPTIONS]"
    print ""
    print "OPTIONS:"
    print "  -v cols=COL1,COL2,...       Columns to display (use * for all)"
    print "  -v cols=COL1:W1,COL2:W2     Columns with custom widths"
    print "  -v noheader=1               First line is data (no header row)"
    print "  -v headers=COL1,COL2,...    Header names for noheader mode"
    print "  -v srno=1                   Add serial number column (Sr.#)"
    print "  -v help=1                   Show this help message"
    print ""
    print "EXAMPLES:"
    print ""
    print "  # Basic usage (data has header row):"
    print "  eq ESC_TRP_Closed | awk -F \"\\t\" -f et_data_in_col.awk -v cols=INCIDENT,STATE"
    print ""
    print "  # Custom column widths:"
    print "  eq queryname | awk -F \"\\t\" -f et_data_in_col.awk -v cols=INCIDENT:20,STATE:30,ABSTRACT"
    print ""
    print "  # Display all columns:"
    print "  eq queryname | awk -F \"\\t\" -f et_data_in_col.awk -v \"cols=*\""
    print ""
    print "  # No-header mode (for esql output without headers):"
    print "  esql -r queryname | awk -F \"\\t\" -f et_data_in_col.awk \\"
    print "      -v noheader=1 -v headers=INCIDENT,STATE,ABSTRACT"
    print ""
    print "  # No-header mode with custom widths:"
    print "  esql -r queryname | awk -F \"\\t\" -f et_data_in_col.awk \\"
    print "      -v noheader=1 -v headers=INCIDENT,STATE,ABSTRACT \\"
    print "      -v cols=INCIDENT:15,STATE:25,ABSTRACT:80"
    print ""
    print "  # Filter columns in noheader mode:"
    print "  esql -r query | awk -F \"\\t\" -f et_data_in_col.awk \\"
    print "      -v noheader=1 -v headers=INCIDENT,STATE,ABSTRACT \\"
    print "      -v cols=INCIDENT:12,ABSTRACT:40"
    print ""
    print "  # Select subset of columns (headers=full structure, cols=display selection):"
    print "  # Data has 4 columns, but display only INCIDENT and FI_list"
    print "  cat data.txt | awk -F \"\\t\" -f et_data_in_col.awk \\"
    print "      -v noheader=1 -v headers=INCIDENT,Assigned_to,User,FI_list \\"
    print "      -v cols=INCIDENT:15,FI_list:60 -v srno=1"
    print ""
    print "NOTES:"
    print "  - Column matching is case-insensitive"
    print "  - Custom width format: COLUMN_NAME:WIDTH (e.g., INCIDENT:20)"
    print "  - Widths are specified in cols, not headers"
    print "  - headers = full data structure (all columns in order)"
    print "  - cols = columns to display (can be a subset of headers)"
    print "  - In noheader mode, headers must match the column order in data"
    print ""
}

# Function to get column width (custom > default > fallback)
function get_width(colName) {
    if (CustomWidth[colName] != "") {
        return CustomWidth[colName]
    } else if (ColumnWidth[colName] != "") {
        return ColumnWidth[colName]
    } else {
        return ColumnWidth["DEFAULT"]
    }
}

function print_seperator(width,    _j) {
    for(_j=1;_j<=width;_j++)
        printf("-");
    printf("\n");
}

# Skip empty lines
/^[[:space:]]*$/ { next }

!header_done {
    # noheader mode: first line is data, headers provided via -v headers=...
    if (noheader == 1 && headers != "") {
        # Use provided headers for column names (case-insensitive lookup)
        for (i = 1; i <= HeaderCount; i++) {
            ix[tolower(HeaderNames[i])] = i
        }
        
        # If cols not set or *, use all headers
        if (cols == "" || cols == "*") {
            for (i = 1; i <= HeaderCount; i++) {
                out[i] = HeaderNames[i]
            }
            Columns = HeaderCount
        }
        
        # Validate that all cols exist in headers
        for (i = 1; i <= Columns; i++) {
            colLower = tolower(out[i])
            if (!(colLower in ix)) {
                print "Error: Column '" out[i] "' not found in headers" > "/dev/stderr"
                exit 1
            }
        }
        
        # Calculate total width: 1 (initial |) + sum of (width + 2) per column
        TotalWidth = 1
        if (srno == 1) TotalWidth = TotalWidth + SRNO_WIDTH + 2
        for (i = 1; i <= Columns; i++) {
            TotalWidth = TotalWidth + get_width(out[i]) + 2
        }
        
        # Print header separator and header row
        print_seperator(TotalWidth)
        printf "|"
        if (srno == 1) printf " %-*s|", SRNO_WIDTH, "Sr.#"
        for (i = 1; i <= Columns; i++) {
            w = get_width(out[i])
            printf " %-*s|", w, substr(out[i], 1, w)
        }
        print ""
        print_seperator(TotalWidth)
        
        # Print first data row (first line is data, not header)
        row_num++
        data_rows++
        printf "|"
        if (srno == 1) printf " %-*d|", SRNO_WIDTH, row_num
        for (i = 1; i <= Columns; i++) {
            w = get_width(out[i])
            colIdx = ix[tolower(out[i])]
            printf " %-*s|", w, substr($colIdx, 1, w)
        }
        print ""
        header_done = 1
        next
    }
    
    # Normal mode: first line is header row (case-insensitive lookup)
    if (cols == "*") {
        for (i = 1; i <= NF; i++)
            out[i] = $i
        Columns = NF
    }

    # Build case-insensitive index mapping
    for (i = 1; i <= NF; i++)
        ix[tolower($i)] = i

    # Validate that all cols exist in headers
    for (i = 1; i <= Columns; i++) {
        colLower = tolower(out[i])
        if (!(colLower in ix)) {
            print "Error: Column '" out[i] "' not found in data headers" > "/dev/stderr"
            exit 1
        }
    }

    # Calculate total width: 1 (initial |) + sum of (width + 2) per column
    TotalWidth = 1
    if (srno == 1) TotalWidth = TotalWidth + SRNO_WIDTH + 2
    for (i = 1; i <= Columns; i++) {
        TotalWidth = TotalWidth + get_width(out[i]) + 2
    }

    print_seperator(TotalWidth)

    printf "|"
    if (srno == 1) printf " %-*s|", SRNO_WIDTH, "Sr.#"
    for (i = 1; i <= Columns; i++) {
        w = get_width(out[i])
        colIdx = ix[tolower(out[i])]
        printf " %-*s|", w, substr($colIdx, 1, w)
    }
    print ""
    print_seperator(TotalWidth)
    header_done = 1
    next
}
header_done {
    row_num++
    data_rows++
    printf "|"
    if (srno == 1) printf " %-*d|", SRNO_WIDTH, row_num
    for (i = 1; i <= Columns; i++) {
        w = get_width(out[i])
        colIdx = ix[tolower(out[i])]
        printf " %-*s|", w, substr($colIdx, 1, w)
    }
    print ""
}



END {
    # Skip footer if help was shown
    if (help == 1) exit 0
    
    print_seperator(TotalWidth)
    # Use data_rows for accurate count (excludes empty lines and header)
    printf "\nTotal number of records: %d\n", data_rows
}


# ========== USAGE EXAMPLES ==========
#
# BASIC USAGE (with header row in data):
#   eq ESC_TRP_Closed | grep -v "^Query:" | sed '/^s*$/d' | \
#       awk -F "\t" -f ~/scripts/et_data_in_col.awk -v cols=INCIDENT,STATE
#
# CUSTOM COLUMN WIDTHS (HEADER:WIDTH format):
#   eq queryname | grep -e "^INCIDENT\|^[0-9]" | \
#       awk -F "\t" -f ~/scripts/et_data_in_col.awk -v cols=INCIDENT:20,STATE:30,ABSTRACT
#
#   # INCIDENT=20 chars, STATE=30 chars, ABSTRACT=default width
#
# NO-HEADER MODE (data without header row, provide headers via -v headers):
#   esql -r queryname | \
#       awk -F "\t" -f ~/scripts/et_data_in_col.awk -v noheader=1 \
#           -v headers=INCIDENT,STATE,ABSTRACT -v cols=INCIDENT,STATE
#
# NO-HEADER MODE with custom widths:
#   esql -r queryname | \
#       awk -F "\t" -f ~/scripts/et_data_in_col.awk -v noheader=1 \
#           -v headers=INCIDENT,STATE,ABSTRACT -v cols=INCIDENT:15,STATE:25,ABSTRACT:80
#
#   # cols can also have custom widths to override headers
#   esql -r queryname | \
#       awk -F "\t" -f ~/scripts/et_data_in_col.awk -v noheader=1 \
#           -v headers=INCIDENT,STATE,ABSTRACT -v cols=INCIDENT:20,STATE:30
#
# DISPLAY ALL COLUMNS:
#   eq queryname | awk -F "\t" -f ~/scripts/et_data_in_col.awk -v cols='*'
#
# PARAMETERS:
#   -v cols=COL1,COL2,...       Columns to display (use * for all)
#   -v cols=COL1:W1,COL2:W2     Columns with custom widths
#   -v noheader=1               Data has no header row
#   -v headers=COL1,COL2,...    Header names for noheader mode (no widths)

