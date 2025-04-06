#!/bin/bash
# Ex: for j in ABC-242332, ABC-241401, ABC-242929, ABC-241522, ABC-241528, ABC-241533; do echo $j | tr ',' ' ' | while read f; do j.getDet $f; done; done | ./j.getDetInTblForm.sh
# Ex: j.getDet ABC-242332  | ./j.getDetInTblForm.sh

grep -E "^JiraID|^Summary|^Assignee|^Reporter|^IssueType|^IssueStatus|^Labels" | awk '
/^JiraID:/      { id = $2 }
/^Summary:/     { sub(/^Summary:[ \t]*/, "", $0); summary = $0 }
/^Assignee:/    { assignee = $2 }
/^Reporter:/    { reporter = $2 }
/^IssueType:/   { type = $2 }
/^IssueStatus:/ { status = $2 }
/^Labels:/      { { sub(/^Labels:[ \t]*/, "", $0); labels = $0 }
    data[entry++] = id "|" summary "|" assignee "|" reporter "|" type "|" status "|" labels
    if (length(id) > max_id) max_id = length(id)
    if (length(summary) > max_summary) max_summary = length(summary)
    if (length(assignee) > max_assignee) max_assignee = length(assignee)
    if (length(reporter) > max_reporter) max_reporter = length(reporter)
    if (length(type) > max_type) max_type = length(type)
    if (length(status) > max_status) max_status = length(status)
    if (length(labels) > max_labels) max_labels = length(labels)
}
END {
    # Header length constants
    header_id      = length("JiraID")
    header_summary = length("Summary")
    header_assignee = length("Assignee")
    header_reporter = length("Reporter")
    header_type     = length("Type")
    header_status   = length("Status")
    header_labels   = length("Labels")

    # Adjust final column widths
    max_id      = (max_id      > header_id      ? max_id      : header_id)
    max_summary = (max_summary > header_summary ? max_summary : header_summary)
    max_assignee= (max_assignee> header_assignee? max_assignee: header_assignee)
    max_reporter= (max_reporter> header_reporter? max_reporter: header_reporter)
    max_type    = (max_type    > header_type    ? max_type    : header_type)
    max_status  = (max_status  > header_status  ? max_status  : header_status)
    max_labels  = (max_labels  > header_labels  ? max_labels  : header_labels)

    # Print top separator
    printf("|-%s-|-%s-|-%s-|-%s-|-%s-|-%s-|-%s-|\n", \
        rep(max_id), rep(max_summary), rep(max_assignee), rep(max_reporter), \
        rep(max_type), rep(max_status), rep(max_labels))

    # Print header
    printf("| %-*s | %-*s | %-*s | %-*s | %-*s | %-*s | %-*s |\n", \
        max_id, "JiraID", max_summary, "Summary", max_assignee, "Assignee", max_reporter, "Reporter", \
        max_type, "Type", max_status, "Status", max_labels, "Labels")

    # Print separator after header
    printf("|-%s-|-%s-|-%s-|-%s-|-%s-|-%s-|-%s-|\n", \
        rep(max_id), rep(max_summary), rep(max_assignee), rep(max_reporter), \
        rep(max_type), rep(max_status), rep(max_labels))

    # Print rows
    for (i = 0; i < entry; i++) {
        split(data[i], f, "|")
        printf("| %-*s | %-*s | %-*s | %-*s | %-*s | %-*s | %-*s |\n", \
            max_id, f[1], max_summary, f[2], max_assignee, f[3], max_reporter, f[4], \
            max_type, f[5], max_status, f[6], max_labels, f[7])
    }

    # Print bottom separator
    printf("|-%s-|-%s-|-%s-|-%s-|-%s-|-%s-|-%s-|\n", \
        rep(max_id), rep(max_summary), rep(max_assignee), rep(max_reporter), \
        rep(max_type), rep(max_status), rep(max_labels))
}

# Function to repeat "-" n times
function rep(n,    out, i) {
    out = ""
    for (i = 0; i < n; i++) out = out "-"
    return out
}'
