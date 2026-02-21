#!/usr/bin/env python3
"""
Python replacement for et_data_in_col.awk for data WITHOUT headers.

This script processes data that doesn't have headers in the first line.
Instead, headers must be provided as command-line arguments.

The key difference from equery_formatter.py is:
- equery_formatter.py expects the first line to be headers (from equery output)
- esql_formatter.py requires headers to be passed via --headers argument

Supports both LOCAL and REMOTE execution modes.

USAGE:
    esql_formatter.py [--file FILE | --stdin | --command COMMAND | --query QUERYNAME] --headers HEADERS [--cols COLS] [--ssh SSH]

REQUIRED ARGUMENTS:
    --headers, -H     Comma-separated header names in order (e.g., INCIDENT,STATE,ABSTRACT)
                     Headers MUST match the order of columns in the data.
                     Optional: specify custom width with HEADER:WIDTH format
                     Example: INCIDENT:20,STATE:30,ABSTRACT (ABSTRACT uses default width)

INPUT SOURCE (one required):
    --file, -f       Read data from a file
    --stdin          Read data from standard input
    --command        Execute a command and format its output
    --query, -r      Run a named esql query (executes: esql -r <queryname>)

OPTIONAL ARGUMENTS:
    --cols, -c       Comma-separated column names to display (subset/reorder of headers)
                     Use "*" to display all columns (default)
    --ssh            SSH target for remote execution (format: user@host)
                     Valid with --command or --query options

EXAMPLES:

1. Basic file processing with headers:
   $ cat data.txt
   12345	Open	Bug in the system
   67890	Closed	Feature request
   
   $ ./esql_formatter.py --file data.txt --headers INCIDENT,STATE,ABSTRACT
   ---------------------------------------------------------------------------
   | INCIDENT | STATE      | ABSTRACT                                                     |
   ---------------------------------------------------------------------------
   | 12345    | Open       | Bug in the system                                            |
   | 67890    | Closed     | Feature request                                              |
   ---------------------------------------------------------------------------
   
   Total number of records: 2

2. Process stdin with headers:
   $ cat data.txt | ./esql_formatter.py --stdin --headers ID,NAME,STATUS,DATE
   $ echo -e "1001\tJohn\tActive\t2026-01-19\n1002\tJane\tInactive\t2026-01-18" | \
       ./esql_formatter.py --stdin --headers ID,NAME,STATUS,DATE

3. Select and reorder specific columns:
   $ ./esql_formatter.py --file data.txt --headers INCIDENT,STATE,ABSTRACT,DATE \
       --cols STATE,INCIDENT
   -----------------------
   | STATE      | INCIDENT |
   -----------------------
   | Open       | 12345    |
   | Closed     | 67890    |
   -----------------------

4. Local command execution:
   $ ./esql_formatter.py --command "psql -t -c 'SELECT id, name, status FROM users'" \
       --headers ID,NAME,STATUS

5. Remote SQL query via SSH:
   $ ./esql_formatter.py --command "mysql -N -e 'SELECT * FROM incidents'" \
       --ssh user@dbserver.com --headers INCIDENT,STATE,PRIORITY,ABSTRACT

6. PostgreSQL query with formatting:
   $ ./esql_formatter.py \
       --command "psql -d mydb -t -A -F$'\t' -c 'SELECT incident_id, state, created_date FROM tickets'" \
       --headers INCIDENT,STATE,DATE --cols INCIDENT,STATE

7. Remote MySQL query:
   $ ./esql_formatter.py \
       --command "mysql -h localhost -u user -p'password' -D mydb -N -B -e 'SELECT * FROM issues'" \
       --ssh user@remote.com --headers ID,TITLE,STATUS,ASSIGNEE

8. Process query output saved in file:
   $ psql -t -c "SELECT * FROM incidents" > /tmp/data.txt
   $ ./esql_formatter.py --file /tmp/data.txt --headers INCIDENT,STATE,PRIORITY

9. Pipeline processing:
   $ grep "^[0-9]" raw_data.txt | \
       ./esql_formatter.py --stdin --headers INCIDENT,STATE,ABSTRACT --cols INCIDENT,STATE

10. Display all columns (default behavior):
    $ ./esql_formatter.py --file data.txt --headers COL1,COL2,COL3,COL4
    # or explicitly
    $ ./esql_formatter.py --file data.txt --headers COL1,COL2,COL3,COL4 --cols '*'

11. Run a named esql query:
    $ ./esql_formatter.py --query my_incidents --headers INCIDENT,STATE,ABSTRACT
    # or using short form
    $ ./esql_formatter.py -r my_incidents -H INCIDENT,STATE,ABSTRACT --cols INCIDENT,STATE

12. Custom column widths:
    $ ./esql_formatter.py --file data.txt --headers INCIDENT:20,STATE:30,ABSTRACT
    # INCIDENT=20 chars, STATE=30 chars, ABSTRACT=default width (90)
    
    $ ./esql_formatter.py -r my_query -H INCIDENT:15,STATE:25,PRIORITY:5,ABSTRACT:100

13. Run esql query on a remote system:
    $ ./esql_formatter.py -r my_incidents --ssh user@remote.com -H INCIDENT,STATE,ABSTRACT
    # Executes: ssh user@remote.com "esql -r my_incidents"
    
    $ ./esql_formatter.py --query open_tickets --ssh admin@dbserver.com \
        --headers INCIDENT:15,STATE,PRIORITY,ABSTRACT:80 --cols INCIDENT,STATE,ABSTRACT

COMMON USE CASES:

A. Format MySQL query output:
   mysql -N -e "SELECT id, name, email FROM users" | \
     ./esql_formatter.py --stdin --headers ID,NAME,EMAIL

B. Format PostgreSQL query output:
   psql -t -A -F$'\t' -c "SELECT * FROM orders" | \
     ./esql_formatter.py --stdin --headers ORDER_ID,CUSTOMER,AMOUNT,DATE

C. Format remote database query:
   ./esql_formatter.py \
     --command "psql -t -c 'SELECT * FROM tickets WHERE state='\''Open'\'''" \
     --ssh dbuser@dbserver.com \
     --headers INCIDENT,STATE,REPORTER,DATE

D. Custom column selection:
   cat raw_report.txt | \
     ./esql_formatter.py --stdin \
     --headers ID,NAME,STATUS,PRIORITY,DATE,OWNER \
     --cols ID,STATUS,OWNER

NOTES:
- Input data should be TAB-separated (TSV format)
- Headers must be in the SAME ORDER as columns in the data
- Use --cols to select which headers to display and in what order
- All data lines are processed (no header line expected in data)
- Empty lines are automatically skipped

Original AWK equivalent:
    cat data.txt | awk -F "\t" -f ~/scripts/et_data_in_col.awk -v noheader=1 -v cols=INCIDENT,STATE
"""

import sys
import subprocess
import argparse
from typing import List, Dict, Optional
import re


class EsqlFormatter:
    """Format SQL output (without headers) into a table with customizable columns."""

    # Predefined column widths matching the AWK script
    COLUMN_WIDTHS = {
        'ABSTRACT': 90,
        'CATEGORY': 20,
        'CHANGED_BY': 20,
        'COMPONENT': 30,
        'DATE_CLOSED': 11,
        'DATE_FIXED': 11,
        'DATE_OPENED': 14,
        'DEFAULT': 12,
        'INCIDENT': 8,
        'KEYWORD': 20,
        'LAST_CHANGED': 11,
        'PLATFORM': 13,
        'PRIORITY': 3,
        'PRODUCT': 10,
        'PROGRESS_STATUS': 40,
        'REPORTER': 20,
        'SEVERITY': 3,
        'STATE': 10,
        'SUBSCRIBE': 40,
        'TYPE': 17,
        'TARGET_BUILD': 13,
        'TARGET_VERSION': 10,
        'USER_DEFINED': 20,
        'USER_DEFINED2': 30,
        'VERSION': 8,
    }

    def __init__(self, headers: List[str], columns: Optional[List[str]] = None,
                 custom_widths: Optional[Dict[str, int]] = None):
        """
        Initialize formatter with specified headers and optional column selection.

        Args:
            headers: List of header names in order (matches data columns)
            columns: List of column names to display, or None for all columns
            custom_widths: Dict mapping header names to custom widths (optional)
        """
        self.headers = headers
        self.columns = columns
        self.custom_widths = custom_widths or {}
        self.column_indices = {}
        self.display_columns = []
        self.column_widths = {}
        
        self._setup_columns()

    def get_column_width(self, column_name: str) -> int:
        """Get the width for a column. Priority: custom > predefined > default."""
        if column_name in self.custom_widths:
            return self.custom_widths[column_name]
        return self.COLUMN_WIDTHS.get(column_name, self.COLUMN_WIDTHS['DEFAULT'])

    def _setup_columns(self) -> None:
        """Setup column mappings and display columns."""
        # Create index mapping for quick lookup
        self.column_indices = {col: idx for idx, col in enumerate(self.headers)}

        # Determine which columns to display
        if self.columns is None or '*' in self.columns:
            self.display_columns = self.headers
        else:
            # Only include columns that exist in the header
            self.display_columns = [col for col in self.columns if col in self.column_indices]

            # Warn about missing columns
            missing = set(self.columns) - set(self.headers)
            if missing:
                print(f"Warning: Columns not found in headers: {', '.join(missing)}",
                      file=sys.stderr)

        # Setup column widths
        for col in self.display_columns:
            self.column_widths[col] = self.get_column_width(col)

    def print_separator(self) -> None:
        """Print a separator line."""
        total_width = sum(self.column_widths.values()) + len(self.display_columns) * 3 + 1
        print('-' * total_width)

    def print_row(self, values: List[str]) -> None:
        """
        Print a row with proper formatting.

        Args:
            values: List of values corresponding to all columns
        """
        print('|', end='')
        for col in self.display_columns:
            idx = self.column_indices[col]
            width = self.column_widths[col]

            # Get value and truncate if needed
            value = values[idx] if idx < len(values) else ''
            truncated = value[:width] if len(value) > width else value

            print(f' {truncated:<{width}} |', end='')
        print()

    def format_data(self, lines: List[str]) -> None:
        """
        Format and print the data.

        Args:
            lines: List of data lines (NO header line)
        """
        if not lines:
            print("No data to format")
            return

        if not self.display_columns:
            print("No valid columns to display")
            return

        # Print header (from provided headers)
        self.print_separator()
        self.print_row(self.headers)
        self.print_separator()

        # Print data rows
        record_count = 0
        for line in lines:
            line = line.strip()
            if line:  # Skip empty lines
                values = line.split('\t')
                self.print_row(values)
                record_count += 1

        # Print footer
        self.print_separator()
        print(f"\nTotal number of records: {record_count}")


def run_command(command: str, ssh_target: Optional[str] = None) -> List[str]:
    """
    Execute a command and return output.
    Supports both LOCAL and REMOTE (SSH) execution.

    Args:
        command: Command to execute
        ssh_target: SSH target in format user@host (e.g., user@server.com)
                   If None, runs locally

    Returns:
        List of output lines
    """
    try:
        # Build full command (local or via SSH)
        if ssh_target:
            # ===== REMOTE EXECUTION: Execute via SSH =====
            cmd = ['ssh', ssh_target, command]
            print(f"[REMOTE] Running via SSH on {ssh_target}: {command}", file=sys.stderr)
        else:
            # ===== LOCAL EXECUTION =====
            cmd = command.split()
            print(f"[LOCAL] Running: {command}", file=sys.stderr)

        # Execute command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # Return all non-empty lines
        lines = [line.strip() for line in result.stdout.split('\n') if line.strip()]

        if not lines:
            print("Warning: No data lines found in command output", file=sys.stderr)
        else:
            print(f"[INFO] Found {len(lines)} data rows", file=sys.stderr)

        return lines

    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {command}", file=sys.stderr)
        if e.stderr:
            print(f"Error output: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


def read_from_file(filepath: str) -> List[str]:
    """
    Read data from a file.

    Args:
        filepath: Path to the file

    Returns:
        List of lines from the file
    """
    try:
        with open(filepath, 'r') as f:
            lines = [line.strip() for line in f if line.strip()]
        return lines
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)


def read_from_stdin() -> List[str]:
    """
    Read data from stdin.

    Returns:
        List of lines from stdin
    """
    lines = [line.strip() for line in sys.stdin if line.strip()]
    return lines


def parse_list_arg(arg: str) -> List[str]:
    """
    Parse comma-separated argument.

    Args:
        arg: Comma-separated values

    Returns:
        List of values
    """
    return [item.strip() for item in arg.split(',') if item.strip()]


def parse_headers_with_widths(arg: str) -> tuple:
    """
    Parse headers with optional width specification.
    
    Format: HEADER or HEADER:WIDTH
    Example: "INCIDENT:20,STATE:30,ABSTRACT" -> 
             headers=['INCIDENT','STATE','ABSTRACT'], widths={'INCIDENT':20,'STATE':30}

    Args:
        arg: Comma-separated headers with optional :WIDTH suffix

    Returns:
        Tuple of (list of header names, dict of custom widths)
    """
    headers = []
    custom_widths = {}
    
    for item in arg.split(','):
        item = item.strip()
        if not item:
            continue
        
        if ':' in item:
            parts = item.split(':', 1)
            header_name = parts[0].strip()
            try:
                width = int(parts[1].strip())
                if width > 0:
                    custom_widths[header_name] = width
                else:
                    print(f"Warning: Invalid width for {header_name}, using default", file=sys.stderr)
            except ValueError:
                print(f"Warning: Invalid width '{parts[1]}' for {header_name}, using default", file=sys.stderr)
            headers.append(header_name)
        else:
            headers.append(item)
    
    return headers, custom_widths


def parse_columns(cols_arg: Optional[str]) -> Optional[List[str]]:
    """
    Parse column specification.

    Args:
        cols_arg: Comma-separated column names or '*' or None

    Returns:
        List of column names or None for all columns
    """
    if not cols_arg or cols_arg == '*':
        return None
    return parse_list_arg(cols_arg)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Format data (WITHOUT headers) into a nicely formatted table',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process file with headers specified
  %(prog)s --file data.txt --headers INCIDENT,STATE,ABSTRACT
  
  # Process stdin with headers
  cat data.txt | %(prog)s --stdin --headers ID,NAME,STATUS,DATE
  
  # Select specific columns in specific order
  %(prog)s --file data.txt --headers INCIDENT,STATE,ABSTRACT --cols STATE,INCIDENT
  
  # Remote command execution
  %(prog)s --command "mysql -e 'SELECT * FROM table'" --ssh user@server.com --headers ID,NAME,STATUS
  
  # Local command execution
  %(prog)s --command "psql -t -c 'SELECT * FROM table'" --headers ID,NAME,STATUS
  
  # Run named esql query
  %(prog)s --query my_incidents --headers INCIDENT,STATE,ABSTRACT
  %(prog)s -r my_incidents -H INCIDENT,STATE,ABSTRACT --cols INCIDENT,STATE
  
  # Custom column widths (HEADER:WIDTH format)
  %(prog)s --file data.txt --headers INCIDENT:20,STATE:30,ABSTRACT

Note: Headers MUST be provided via --headers in the same order as data columns.
      Use HEADER:WIDTH format for custom widths (e.g., INCIDENT:20,STATE:30,ABSTRACT).
      Use --cols to select which columns to display and in what order.
        """
    )

    # Input source (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=False)
    input_group.add_argument(
        '--file', '-f',
        help='Read from file'
    )
    input_group.add_argument(
        '--stdin',
        action='store_true',
        help='Read from stdin'
    )
    input_group.add_argument(
        '--command',
        help='Command to execute (output should be tab-separated data without headers)'
    )
    input_group.add_argument(
        '--query', '-r',
        help='Named esql query to run (executes: esql -r <queryname>)'
    )

    # Headers (REQUIRED)
    parser.add_argument(
        '--headers', '-H',
        required=True,
        help='REQUIRED: Comma-separated header names in order (e.g., INCIDENT,STATE,ABSTRACT)'
    )

    # SSH target for remote execution
    parser.add_argument(
        '--ssh',
        help='SSH target for remote execution (format: user@host). Use with --command or --query.'
    )

    # Column specification
    parser.add_argument(
        '--cols', '-c',
        help='Comma-separated column names to display (use "*" for all columns). If not specified, displays all headers.',
        default=None
    )

    args = parser.parse_args()

    # Validate input
    if not args.file and not args.stdin and not args.command and not args.query:
        parser.error("Must specify either --file, --stdin, --command, or --query")

    # Validate SSH usage
    if args.ssh and not args.command and not args.query:
        parser.error("--ssh can only be used with --command or --query")

    # Parse headers (with optional custom widths)
    headers, custom_widths = parse_headers_with_widths(args.headers)
    if not headers:
        parser.error("--headers cannot be empty")

    # Parse columns
    columns = parse_columns(args.cols)

    # Get data
    if args.stdin:
        print("[INFO] Reading from stdin", file=sys.stderr)
        lines = read_from_stdin()
    elif args.file:
        print(f"[INFO] Reading from file: {args.file}", file=sys.stderr)
        lines = read_from_file(args.file)
    elif args.command:
        lines = run_command(args.command, ssh_target=args.ssh)
    elif args.query:
        esql_command = f"esql -r {args.query}"
        lines = run_command(esql_command, ssh_target=args.ssh)
    else:
        parser.error("No input source specified")

    # Format and display
    formatter = EsqlFormatter(headers=headers, columns=columns, custom_widths=custom_widths)
    formatter.format_data(lines)


if __name__ == '__main__':
    main()
