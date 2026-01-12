#!/usr/bin/env python3
"""
Python replacement for et_data_in_col.awk with equery integration.

This script executes equery commands (locally or remotely via SSH) and formats 
the tab-separated output into a nicely formatted table with customizable columns.

Supports both LOCAL and REMOTE execution modes.

Usage Examples:
    # LOCAL EXECUTION - Run equery locally
    ./equery_formatter.py ESC_TRP_Closed --cols INCIDENT,STATE
    ./equery_formatter.py my_query --cols '*'
    ./equery_formatter.py my_query -u username --cols INCIDENT,STATE

    # REMOTE EXECUTION - Run equery on remote server via SSH
    ./equery_formatter.py my_query --ssh user@server.com
    ./equery_formatter.py my_query --ssh $NIS_USER@$NIS_SERVER --cols INCIDENT,STATE
    ./equery_formatter.py my_query --ssh user@server.com -u username

    # FILE INPUT - Process an existing file (like SR_FI_SH)
    ./equery_formatter.py --file ~/op/SR_FI_SH --cols INCIDENT,STATE,ABSTRACT

    # STDIN - Read from stdin
    cat ~/op/SR_FI_SH | ./equery_formatter.py --stdin --cols INCIDENT,STATE

Original AWK equivalent:
    equery queryname | egrep "^INCIDENT|^[0-9]" | awk -F "\t" -f ~/scripts/et_data_in_col.awk -v cols=INCIDENT,STATE
"""

import sys
import subprocess
import argparse
from typing import List, Dict, Optional
import re


class EqueryFormatter:
    """Format equery output into a table with customizable columns."""

    # Predefined column widths matching the AWK script
    COLUMN_WIDTHS = {
        'ABSTRACT': 60,
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

    def __init__(self, columns: Optional[List[str]] = None):
        """
        Initialize formatter with specified columns.

        Args:
            columns: List of column names to display, or None for all columns
        """
        self.columns = columns
        self.headers = []
        self.column_indices = {}
        self.display_columns = []
        self.column_widths = {}

    def get_column_width(self, column_name: str) -> int:
        """Get the width for a column, using default if not defined."""
        return self.COLUMN_WIDTHS.get(column_name, self.COLUMN_WIDTHS['DEFAULT'])

    def parse_header(self, header_line: str) -> None:
        """
        Parse the header line and setup column mappings.

        Args:
            header_line: Tab-separated header line
        """
        self.headers = header_line.strip().split('\t')
        
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
                print(f"Warning: Columns not found in data: {', '.join(missing)}", 
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
            lines: List of lines from equery output
        """
        if not lines:
            print("No data to format")
            return

        # Parse header
        self.parse_header(lines[0])

        if not self.display_columns:
            print("No valid columns to display")
            return

        # Print header
        self.print_separator()
        self.print_row(self.headers)
        self.print_separator()

        # Print data rows
        record_count = 0
        for line in lines[1:]:
            line = line.strip()
            if line:  # Skip empty lines
                values = line.split('\t')
                self.print_row(values)
                record_count += 1

        # Print footer
        self.print_separator()
        print(f"\nTotal number of records: {record_count}")


def run_equery(query_name: str, ssh_target: Optional[str] = None, 
               user_flag: Optional[str] = None) -> List[str]:
    """
    Execute equery command and return filtered output.
    Supports both LOCAL and REMOTE (SSH) execution.

    Args:
        query_name: Name of the saved query
        ssh_target: SSH target in format user@host (e.g., user@server.com)
                   If None, runs locally
        user_flag: Username for equery -u flag (user impersonation)

    Returns:
        List of output lines (filtered to match INCIDENT header or numeric lines)
    """
    try:
        # Build equery command with optional -u flag
        equery_cmd_parts = ['equery']
        if user_flag:
            equery_cmd_parts.extend(['-u', user_flag])
        equery_cmd_parts.append(query_name)
        
        # Build full command (local or via SSH)
        if ssh_target:
            # ===== REMOTE EXECUTION: Execute via SSH =====
            cmd = ['ssh', ssh_target] + equery_cmd_parts
            print(f"[REMOTE] Running via SSH on {ssh_target}", file=sys.stderr)
        else:
            # ===== LOCAL EXECUTION: Try local equery commands =====
            cmd = None
            for equery_path in ['/usr/local/bin/equery', 'equery', '/usr/local/bin/eq', 'eq']:
                try:
                    # Check if command exists
                    which_result = subprocess.run(
                        ['which', equery_path],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    if which_result.returncode == 0 or equery_path in ['equery', 'eq']:
                        equery_cmd_parts[0] = equery_path
                        cmd = equery_cmd_parts
                        print(f"[LOCAL] Running: {' '.join(cmd)}", file=sys.stderr)
                        break
                except Exception:
                    continue
            
            if cmd is None:
                print("Error: equery command not found locally.", file=sys.stderr)
                print("  Tried: /usr/local/bin/equery, equery, /usr/local/bin/eq, eq", file=sys.stderr)
                print("  Hint: Use --ssh user@server to run on remote server instead", file=sys.stderr)
                sys.exit(1)
        
        # Execute command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Filter output: only lines starting with INCIDENT or digits (matching egrep "^INCIDENT|^[0-9]")
        lines = []
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line and (line.startswith('INCIDENT') or (line and line[0].isdigit())):
                lines.append(line)
        
        if not lines:
            print("Warning: No data lines found in equery output", file=sys.stderr)
        else:
            print(f"[INFO] Found {len(lines)} lines ({len(lines)-1} data rows)", file=sys.stderr)
        
        return lines
        
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {' '.join(cmd)}", file=sys.stderr)
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
    return [col.strip() for col in cols_arg.split(',')]


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Format equery output into a nicely formatted table (LOCAL or REMOTE execution)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # LOCAL EXECUTION - Run equery locally
  %(prog)s ESC_TRP_Closed --cols INCIDENT,STATE
  %(prog)s my_query --cols '*'
  %(prog)s my_query -u username --cols INCIDENT,STATE

  # REMOTE EXECUTION - Run equery on remote server via SSH
  %(prog)s my_query --ssh user@server.com
  %(prog)s my_query --ssh user@server.com --cols INCIDENT,STATE
  %(prog)s my_query --ssh user@server.com -u username --cols INCIDENT,STATE

  # FILE INPUT - Process an existing file
  %(prog)s --file ~/op/SR_FI_SH --cols INCIDENT,STATE,ABSTRACT

  # STDIN - Read from stdin
  cat ~/op/SR_FI_SH | %(prog)s --stdin --cols INCIDENT,STATE

Shell function equivalents:
  # Remote execution
  equery_runner() { 
    ssh $NIS_USER@$NIS_SERVER equery $1 | egrep "^INCIDENT|^[0-9]" | \\
      awk -F"\\t" -f ~/.vim/scripts/et_data_in_col.awk -v cols=*
  }
  
  # Local execution
  equery my_query | egrep "^INCIDENT|^[0-9]" | \\
    awk -F"\\t" -f ~/.vim/scripts/et_data_in_col.awk -v cols=INCIDENT,STATE
        """
    )

    # Input source (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=False)
    input_group.add_argument(
        'query_name',
        nargs='?',
        help='Name of the equery to run'
    )
    input_group.add_argument(
        '--file', '-f',
        help='Read from file instead of running equery'
    )
    input_group.add_argument(
        '--stdin',
        action='store_true',
        help='Read from stdin'
    )

    # SSH target for remote execution
    parser.add_argument(
        '--ssh',
        help='SSH target to run equery on (format: user@host). If not specified, runs locally.'
    )

    # User impersonation flag
    parser.add_argument(
        '-u',
        dest='user',
        help='Username for equery -u flag (user impersonation)'
    )

    # Column specification
    parser.add_argument(
        '--cols', '-c',
        help='Comma-separated column names to display (use "*" for all columns)',
        default=None
    )

    args = parser.parse_args()

    # Validate input
    if not args.query_name and not args.file and not args.stdin:
        parser.error("Must specify either query_name, --file, or --stdin")

    # Parse columns
    columns = parse_columns(args.cols)

    # Get data
    if args.stdin:
        print("[INFO] Reading from stdin", file=sys.stderr)
        lines = read_from_stdin()
    elif args.file:
        print(f"[INFO] Reading from file: {args.file}", file=sys.stderr)
        lines = read_from_file(args.file)
    else:
        lines = run_equery(args.query_name, ssh_target=args.ssh, user_flag=args.user)

    # Format and display
    formatter = EqueryFormatter(columns=columns)
    formatter.format_data(lines)


if __name__ == '__main__':
    main()
