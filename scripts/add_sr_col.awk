#!/usr/bin/awk -f

BEGIN {
    FS="|"
    OFS="|"
    sr = 0
    header_done = 0
}

# Separator line
/^[[:space:]]*\+/ {
    sub(/^\+/, "+-----+", $0)
    print
    next
}

# Header row (first | row only)
!header_done && /^\|/ {
    print "| Sr. " $0
    header_done = 1
    next
}

# Data rows
/^\|/ {
    sr++
    printf "| %3d |", sr
    for (i = 2; i <= NF - 1; i++) {
        printf "%s|", $i
    }
    print ""
    next
}

# Anything else
{
    print
}

