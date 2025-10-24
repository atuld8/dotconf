#!/usr/bin/env bash

print_dash() {
        echo -n "--------------------------------------------------------------------------------------------------------------------------------------------------"
        echo "-------------------------------------------------------------------------------------------------------------------------------------"
}

# Function to print the header of the table
print_header_footer() {
    print_dash
printf "%-6s | %-10s | %-100s | %-13s | %-20s | %-20s | %-8s | %-8s | %-10s | %-8s\n" \
       "Serial" "Key" "Summary" "Status" "Assignee" "Reporter" "Priority" "Severity" "IssueType" "Labels"
    print_dash
}


# Function to get issue details from Jira
get_issue_details() {
    local ticket_id=$1
    curl $JIRA_ALIAS_EXTRA_OPT -H "Authorization: Bearer $JIRA_ACC_TOKEN" "https://$JIRA_SERVER_NAME/rest/api/2/issue/${ticket_id}" | \
        jq -r '{
            key: .key,
            summary: .fields.summary,
            status: .fields.status.name,
            assignee: (.fields.assignee.displayName // "Unassigned"),
            reporter: .fields.reporter.displayName,
            priority: .fields.priority.name,
            severity: (.fields.customfield_20303.value // "NA"),
            issuetype: .fields.issuetype.name,
            labels: (.fields.labels | join(", "))
        }| [.key, (.summary | if length > 100 then .[0:97] + "..." else . end), .status, (.assignee | if length > 20 then .[0:20] else . end), (.reporter | if length > 20 then .[0:20] else . end), .priority, .severity, .issuetype, .labels] | @tsv'
    }

# Check if at least one argument is provided
if [ "$#" -eq 0 ]; then
    echo "Usage: $0 JIRA_TICKET_ID [JIRA_TICKET_ID ...]"
    exit 1
fi

# Print the header
print_header_footer

# Initialize a counter for the serial number
serial=1

# Loop through each ticket ID provided as argument
for ticket_id in "$@"; do
    # Get issue details
    details=$(get_issue_details "$ticket_id")

    # Print the details in the desired format
    if [ -n "$details" ]; then
        IFS=$'\t' read -r key summary status assignee reporter priority severity issuetype labels <<< "$details"
        printf "%-6s | %-10s | %-100s | %-13s | %-20s | %-20s | %-8s | %-8s | %-10s | %-8s\n" \
            "$serial" "$key" "$summary" "$status" "$assignee" "$reporter" "$priority" "$severity" "$issuetype" "$labels"
        serial=$((serial + 1))
   else
       echo "Issue $ticket_id not found."
   fi
done

# Print the footer
print_header_footer

