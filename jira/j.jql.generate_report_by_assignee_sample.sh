#!/usr/bin/env bash

# Temporary file to store the data
temp_file=$(mktemp)

# Function to trim leading/trailing whitespaces
trim() {
    echo "$1" | sed 's/^ *//g' | sed 's/ *$//g'
}

# Skip the header and read input table line by line
while IFS='|' read -r emt sr key summary status assignee reporter priority severity issuetype labels; do
    # Skip the header row
    [[ $sr == " Sr. " ]] && continue
    [[ $sr == " " ]] && continue
    [[ $sr == "" ]] && continue

    # Trim leading and trailing whitespaces
    sr=$(echo "$sr" | xargs)
    key=$(echo "$key" | xargs)
    summary=$(trim "$summary")
    assignee=$(echo "$assignee" | xargs)
    priority=$(echo "$priority" | xargs)
    severity=$(echo "$severity" | xargs)
    issuetype=$(echo "$issuetype" | xargs)

    # Append the details to the temp file with priority and assignee for sorting
    echo "$assignee|$priority|$key|$summary|$priority|$severity|$issuetype" >> "$temp_file"
done

# Sort the data first by Assignee, then by Priority (assuming High > Medium > Low)
sort -t'|' -k1,1 -k2,2r "$temp_file" | while IFS='|' read -r assignee priority key summary p s t; do
    # Detect new assignee and print their name
    if [[ "$last_assignee" != "$assignee" ]]; then
        echo -e "\nAssignee: $assignee"
        last_assignee="$assignee"
    fi

        # Print the Jira ticket details for the current assignee
        echo -e -n "\t"
        echo  "$key | $summary (P: $p, S: $s, T: $t)"
    done

# Clean up the temporary file
rm "$temp_file"

