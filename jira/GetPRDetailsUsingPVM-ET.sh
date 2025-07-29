#!/bin/bash

# Script Name: GetPRDetailsUsingPVM-ET.sh
# -----------------------------------------------------------------------------
# Description: Script to extract etrack details and associated pull request
#              information for a given PVM and version.
#
# Usage: ./GetPRDetailsUsingPVM-ET.sh <PVM_ID> [VERSION] [FILE_PATH]
#        <PVM_ID>   : The PVM identifier to query.
#        [VERSION]  : (Optional) The version number to filter results. Default is 11.0.0.1.
#        [FILE_PATH]: (Optional) The path to the file containing PVM details.
#                     Default is $HOME/op/PVM_CVE_IN_Abstract_TB_K0_K001_K1.
# -----------------------------------------------------------------------------

set -euo pipefail

FILE_PATH="$HOME/op/PVM_CVE_IN_Abstract_TB_K0_K001_K1"
VERSION="${VERSION:-11.0.0.1}"
PR_DETAILES_CMD="$HOME/.vim/stash/s.getPRDets.py"

usage() {
    echo "Usage: $0 <PVM_ID> [VERSION] [FILE_PATH]" >&2
    echo "  <PVM_ID>   : The PVM identifier to query." >&2
    echo "  [VERSION]  : (Optional) The version number to filter results. Default is 11.0.0.1." >&2
    echo "  [FILE_PATH]: (Optional) The path to the file containing PVM details. Default is \$HOME/op/PVM_CVE_IN_Abstract_TB_K0_K001_K1." >&2
    exit 1
}

search_and_extract() {
    local pvm_arg="$1"
    local version_arg="$2"
    local file_path_arg="$3"

    while IFS= read -r line; do
        if [[ "$line" == *"$pvm_arg"* && "$line" == *"$version_arg"* ]]; then
            echo "$line" | awk '{print $2}'
            return 0
        fi
    done < "$file_path_arg"
    return 1
}

get_pr_number() {
    local etrack_details="$1"
    # Call x.eprall alias with the extracted etrack details
    pr_output=$(ssh ${RMTCMD_HOST} eprint -v -l -A -f -c -s -u "$etrack_details" 2>/dev/null)

    # Search for 'pull-requests/<number>' pattern and extract the number
    pr_number=$(echo "$pr_output" | grep -oE 'repos/[^/]+/pull-requests/[0-9]+' | awk -F'/' '{print $4}' | head -n1)
    repo_name=$(echo "$pr_output" | grep -oE 'repos/[^/]+/pull-requests/[0-9]+' | awk -F'/' '{print $2}' | head -n1)

    if [[ ! -n "$pr_number" ]]; then
        echo "No pull request number found in x.eprall output." >&2
        exit 1
    fi

    if [[ ! -n "$repo_name" ]]; then
        echo "No repository name found in x.eprall output." >&2
        exit 1
    fi

    echo -e "\n\n"
    echo "Repository name: $repo_name Pull request number: $pr_number"
}

get_etrack_details_for_pvm() {
    local pvm_arg="$1"
    local version_arg="$2"
    local file_path_arg="$3"

    local etrack_details
    if ! etrack_details=$(search_and_extract "$pvm_arg" "$version_arg" "$file_path_arg"); then
        echo "No matching line found for $pvm_arg with version $version_arg" >&2
        return 1
    fi

    if [[ -z "$etrack_details" ]]; then
        echo "Could not extract the etrack details." >&2
        return 1
    fi

    echo "$etrack_details"
}

print_etrack_details() {
    local etrack_details="$1"
    echo "Etrack Details: $etrack_details"

    # Example: Fetch Etrack details using ssh and the ET number
    et_details=$(ssh $RMTCMD_HOST eprint -v "$etrack_details" 2>/dev/null)
    if [[ -n "$et_details" ]]; then
        echo "$et_details"
    else
        echo "No details found for PR #$etrak_details" >&2
        exit 1
    fi
}


get_pr_details() {
    local pr_number="$1"
    local repo_name="$2"

    # Example: Fetch PR details using ssh and the PR number
    pr_details=$($PR_DETAILES_CMD -r "$repo_name" -p "$pr_number")
    if [[ -n "$pr_details" ]]; then
        echo "PR Details:"
        echo "$pr_details"
    else
        echo "No details found for PR #$pr_number" >&2
        exit 1
    fi
}

main() {
    if [[ $# -lt 1 || $# -gt 3 ]]; then
        usage
    fi

    local pvm_arg="$1"
    local version_arg="${2:-$VERSION}"
    local file_path_arg="${3:-$FILE_PATH}"

    if [[ ! -f "$file_path_arg" ]]; then
        echo "File not found: $file_path_arg" >&2
        exit 1
    fi

    if [[ -z "$pvm_arg" ]]; then
        echo "PVM argument is required." >&2
        usage
    fi

    local etrack_details
    etrack_details=$(get_etrack_details_for_pvm "$pvm_arg" "$version_arg" "$file_path_arg") || exit 1

    print_etrack_details "$etrack_details"
    get_pr_number "$etrack_details"

    # Call the function to get PR details using the extracted PR number
    get_pr_details "$pr_number" "$repo_name"
}

main "$@"
