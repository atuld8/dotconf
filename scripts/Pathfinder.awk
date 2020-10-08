# To generate report using this
# equery Pathfinder | grep -e "^[0-9]\{7\}" > query_result_1

tabs 4

awk '
BEGIN {
    verifying[1] = 0;

# Regular
        colours["Black"]="\033[0;30m"
        colours["Red"]="\033[0;31m"
        colours["Green"]="\033[0;32m"
        colours["Yellow"]="\033[0;33m"
        colours["Blue"]="\033[0;34m"
        colours["Purple"]="\033[0;35m"
        colours["Cyan"]="\033[0;36m"
        colours["White"]="\033[0;37m"
#Bold
        colours["BBlack"]="\033[1;30m"
        colours["BRed"]="\033[1;31m"
        colours["BGreen"]="\033[1;32m"
        colours["BYellow"]="\033[1;33m"
        colours["BBlue"]="\033[1;34m"
        colours["BPurple"]="\033[1;35m"
        colours["BCyan"]="\033[1;36m"
        colours["BWhite"]="\033[1;37m"
# High Intensity
        colours["IBlack"]="\033[0;90m"
        colours["IRed"]="\033[0;91m"
        colours["IGreen"]="\033[0;92m"
        colours["IYellow"]="\033[0;93m"
        colours["IBlue"]="\033[0;94m"
        colours["IPurple"]="\033[0;95m"
        colours["ICyan"]="\033[0;96m"
        colours["IWhite"]="\033[0;97m"
# Bold High Intensity
        colours["BIBlack"]="\033[1;90m"
        colours["BIRed"]="\033[1;91m"
        colours["BIGreen"]="\033[1;92m"
        colours["BIYellow"]="\033[1;93m"
        colours["BIBlue"]="\033[1;94m"
        colours["BIPurple"]="\033[1;95m"
        colours["BICyan"]="\033[1;96m"
        colours["BIWhite"]="\033[1;97m"
# Color None
        colours["None"]="\033[0m"
}
function color_format(c,s) {
        return  colours[c] s colours["None"]
}

{
    print "Processing Record - ",NR > "/dev/stderr";
    assigned_to = $2;
    state = $3;
    Type = $4;
    version = $5
    target_ver = $6;
    component = $7;

    if (state !~ /UNASSIGNED/) {

        Total[assigned_to]++;
        Release[target_ver]++;

        # This is state per user and target ver
        if (state ~ /OPEN/)         { open[assigned_to]++;      open_tv[target_ver]++; }
        if (state ~ /FIXED/)        { fixed[assigned_to]++;     fixed_tv[target_ver]++; }
        if (state ~ /WAITING/)      { waiting[assigned_to]++;   waiting_tv[target_ver]++; }
        if (state ~ /WORKING/)      { working[assigned_to]++;   working_tv[target_ver]++; }
        if (state ~ /VERIF/)        { ver[assigned_to]++;       ver_tv[target_ver]++; }
        if (state ~ /FAILED/)       { failed[assigned_to]++;    failed_tv[target_ver]++; }

        # this is type per user
        if ( Type ~ /DEFECT/) defect[assigned_to]++;
        if ( Type ~ /ENHANCEMENT/) enhanc[assigned_to]++;
        if ( Type ~ /TEST_CASE/) test_case[assigned_to]++;
        if ( Type ~ /SERVICE_REQUEST/) {
            sr[assigned_to]++;
            SR_ET[version]++;
            if (state ~ /OPEN/)         {  open_sr[version]++; }
            if (state ~ /FIXED/)        {  fixed_sr[version]++; }
            if (state ~ /WAITING/)      {  waiting_sr[version]++; }
            if (state ~ /WORKING/)      {  working_sr[version]++; }
            if (state ~ /VERIF/)        {  ver_sr[version]++; }
            if (state ~ /FAILED/)       {  failed_sr[version]++; }
        }
    }
    else {
        unassigned_cout++;
        if ( Type ~ /TEST_CASE/) test_case_unassigned_count++;
    }
}

END {

    col_report_name="BBlue"
    print color_format(col_report_name,"\n\n\nPathfinder Etrack Statistic...\n\n\n");

    index_count = asorti(Total, indices);
    # Report 1: User and State per User
    printf color_format(col_report_name,"Report %d: %s\n"), 1, "Etracks assigned to User and its status"
    printf "%s\n", "-----------------------------------------------------------------------------------------------------------------------------------------------------"
    printf "|  %-15s|        %10s        %10s        %10s        %10s        %10s        %10s        |%10s  |\n", "ASSIGNED_TO", "OPEN", "FIXED", "WAITING", "WORKING", "VERIFYING", "FAILED", "TOTAL"
    printf "%s\n", "-----------------------------------------------------------------------------------------------------------------------------------------------------"
#for (assigned_to in Total) {
    for (i = 1; i <= index_count; i++) {
        assigned_to = indices[i];
        printf "|  %-15s|        %10d        %10d        %10d        %10d        %10d        %10d        |%10d  |\n", assigned_to, open[assigned_to], fixed[assigned_to], waiting[assigned_to], working[assigned_to], ver[assigned_to], failed[assigned_to], Total[assigned_to]
        open_count += open[assigned_to];
        fixed_count += fixed[assigned_to];
        waiting_count += waiting[assigned_to];
        working_count += working[assigned_to];
        verifying_count += ver[assigned_to];
        failed_count += failed[assigned_to];
        total_count += Total[assigned_to];
    }
    printf "%s\n", "-----------------------------------------------------------------------------------------------------------------------------------------------------"
        printf "|  %-15s|        %10d        %10d        %10d        %10d        %10d        %10d        |%10d  |\n", "TOTAL", open_count, fixed_count, waiting_count, working_count, verifying_count, failed_count, total_count
    printf "%s\n", "-----------------------------------------------------------------------------------------------------------------------------------------------------"




    # Report 2: User and Type per User
    printf color_format(col_report_name,"\n\n\nReport %d: %s\n"), 2, "Etracks assigned to User and its Type"
    printf "%s\n", "---------------------------------------------------------------------------------------------------------"
    printf "|  %-15s|        %10s        %10s        %20s       |%10s  |\n", "ASSIGNED_TO", "DEFECT", "ENHANCEMENT", "SERVICE_REQUEST", "TOTAL"
    printf "%s\n", "---------------------------------------------------------------------------------------------------------"
    for (i = 1; i <= index_count; i++) {
        assigned_to = indices[i];
        printf "|  %-15s|        %10d        %10d        %20d        |%10d  |\n", assigned_to, defect[assigned_to], enhanc[assigned_to], sr[assigned_to], Total[assigned_to]
        defect_count += defect[assigned_to];
        enhanc_count += enhanc[assigned_to];
        sr_count += sr[assigned_to];
        total_count_2 += Total[assigned_to];
    }
    printf "%s\n", "---------------------------------------------------------------------------------------------------------"
        printf "|  %-15s|        %10d        %10d        %20d        |%10d  |\n", "TOTAL", defect_count, enhanc_count,sr_count,  total_count_2
    printf "%s\n", "---------------------------------------------------------------------------------------------------------"



    index_count = asorti(Release, indices);
    # Report 3: Target Version and State per User
    printf color_format(col_report_name,"\n\n\nReport %d: %s\n"), 3, "Etracks Target Version and State"
    printf "%s\n", "-----------------------------------------------------------------------------------------------------------------------------------------------------"
    printf "|  %-15s|        %10s        %10s        %10s        %10s        %10s        %10s        |%10s  |\n", "TARGET_VER", "OPEN", "FIXED", "WAITING", "WORKING", "VERIFYING", "FAILED", "TOTAL"
    printf "%s\n", "-----------------------------------------------------------------------------------------------------------------------------------------------------"
    for (i = 1; i <= index_count; i++) {
        target_ver = indices[i];
        printf "|  %-15s|        %10d        %10d        %10d        %10d        %10d        %10d        |%10d  |\n", target_ver, open_tv[target_ver], fixed_tv[target_ver], waiting_tv[target_ver], working_tv[target_ver], ver_tv[target_ver], failed_tv[target_ver], Release[target_ver]
        open_tv_count += open_tv[target_ver];
        fixed_tv_count += fixed_tv[target_ver];
        waiting_tv_count += waiting_tv[target_ver];
        working_tv_count += working_tv[target_ver];
        verifying_tv_count += ver_tv[target_ver];
        failed_tv_count += failed_tv[target_ver];
        total_tv_count += Release[target_ver];
    }
    printf "%s\n", "-----------------------------------------------------------------------------------------------------------------------------------------------------"
        printf "|  %-15s|        %10d        %10d        %10d        %10d        %10d        %10d        |%10d  |\n", "TOTAL", open_tv_count, fixed_tv_count, waiting_tv_count, working_tv_count, verifying_tv_count, failed_tv_count, total_tv_count
    printf "%s\n", "-----------------------------------------------------------------------------------------------------------------------------------------------------"


    index_count = asorti(SR_ET, indices);
    # Report 4: SR Version and State
    printf color_format(col_report_name,"\n\n\nReport %d: %s\n"), 4, "Service Request Etracks Version and State"
    printf "%s\n", "-----------------------------------------------------------------------------------------------------------------------------------"
    printf "|  %-15s|        %10s        %10s        %10s        %10s        %10s        |%10s  |\n", "VERSION", "OPEN", "FIXED", "WAITING", "WORKING", "VERIFYING", "TOTAL"
    printf "%s\n", "-----------------------------------------------------------------------------------------------------------------------------------"
    for (i = 1; i <= index_count; i++) {
        version = indices[i];
#        printf "%-15s        %10d        %10d        %10d        %10d        %10d        %10d\n", version, open_sr[version], fixed_sr[version], waiting_sr[version], working_sr[version], ver_sr[version], SR_ET[version]
        printf "|  %-15s|        %10d        %10d        %10d        %10d        %10d        |%10d  |\n", version, open_sr[version], fixed_sr[version], waiting_sr[version], working_sr[version], ver_sr[version], SR_ET[version]
        open_sr_count += open_sr[version];
        fixed_sr_count += fixed_sr[version];
        waiting_sr_count += waiting_sr[version];
        working_sr_count += working_sr[version];
        verifying_sr_count += ver_sr[version];
        total_sr_count += SR_ET[version];
    }
    printf "%s\n", "-----------------------------------------------------------------------------------------------------------------------------------"
#printf "%-15s        %10d        %10d        %10d        %10d        %10d        %10d\n", "TOTAL", open_sr_count, fixed_sr_count, waiting_sr_count, working_sr_count, verifying_sr_count, total_sr_count
        printf "|  %-15s|        %10d        %10d        %10d        %10d        %10d        |%10d  |\n", "TOTAL", open_sr_count, fixed_sr_count, waiting_sr_count, working_sr_count, verifying_sr_count, total_sr_count
    printf "%s\n", "-----------------------------------------------------------------------------------------------------------------------------------"



if ( unassigned_cout > 0 )
        printf color_format("BRed","\n\n\n*** Note: This team has %d Etracks in UNASSIGNED state\n"), unassigned_cout - test_case_unassigned_count

if ( test_case_unassigned_count > 0 )
        printf color_format("BRed","\n\n\n*** Note: This team has %d TEST_CASE Etracks in UNASSIGNED state\n"), test_case_unassigned_count
}' $*

tabs -0
