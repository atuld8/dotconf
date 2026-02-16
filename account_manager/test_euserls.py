#!/usr/bin/env python3
"""
Test script for euserls integration

This script tests the euserls command parsing and execution.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from account_manager.euserls_integration import EuserlsExecutor, EuserInfo


def test_parsing():
    """Test parsing of euserls output"""

    # Sample output from euserls command
    sample_output = """---------------------------------------------------------------
Login           First Last            Phone          Pager          Active
===============================================================================

auser           Amy User          XXX-XXX-XXXX                  Active
Email:  Amy.user@vcompany.com
"""

    print("Testing euserls output parsing...")
    print("=" * 60)

    # Create a minimal executor without full initialization
    import os
    os.environ.setdefault('RMTCMD_HOST', 'test@test.com')  # Set temp value for test

    try:
        executor = EuserlsExecutor()
        user_info = executor._parse_output(sample_output, "auser")

        if user_info:
            print("✓ Parsing successful!")
            print(f"  Login: {user_info.etrack_user_id}")
            print(f"  Name: {user_info.first_name} {user_info.last_name}")
            print(f"  Email: {user_info.email}")
            print(f"  Phone: {user_info.phone}")
            print(f"  Status: {user_info.status}")
            return True
        else:
            print("✗ Parsing failed")
            return False
    finally:
        # Don't unset if it was already set
        if os.environ.get('RMTCMD_HOST') == 'test@test.com':
            del os.environ['RMTCMD_HOST']


def test_live_euserls(etrack_user_id):
    """Test actual euserls command execution"""

    print(f"\nTesting live euserls command for: {etrack_user_id}")
    print("=" * 60)

    try:
        executor = EuserlsExecutor()

        # Check if command is available
        if executor.use_ssh:
            print(f"✓ Will use SSH: {executor.rmtcmd_host}")
        else:
            print(f"✓ euserls found locally at: {executor.euserls_path}")

        # Fetch user info
        print(f"\nFetching user info...")
        user_info = executor.get_user_info(etrack_user_id)

        if user_info:
            print("✓ Successfully fetched user info:")
            print(f"  Login: {user_info.etrack_user_id}")
            print(f"  Name: {user_info.first_name} {user_info.last_name}")
            print(f"  Email: {user_info.email}")
            print(f"  Phone: {user_info.phone}")
            print(f"  Status: {user_info.status}")
            return True
        else:
            print(f"✗ Failed to fetch user info for {etrack_user_id}")
            return False

    except RuntimeError as e:
        print(f"✗ Error: {e}")
        return False


def test_email_only(etrack_user_id):
    """Test fetching just the email"""

    print(f"\nTesting email fetch for: {etrack_user_id}")
    print("=" * 60)

    try:
        executor = EuserlsExecutor()
        email = executor.get_email(etrack_user_id)

        if email:
            print(f"✓ Email: {email}")
            return True
        else:
            print(f"✗ Failed to fetch email")
            return False

    except RuntimeError as e:
        print(f"✗ Error: {e}")
        return False


def main():
    """Main test function"""

    print("╔════════════════════════════════════════════════════════════════╗")
    print("║           EUSERLS INTEGRATION TEST                             ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()

    # Test 1: Parsing
    parsing_ok = test_parsing()

    # Test 2: Live euserls (if user ID provided)
    if len(sys.argv) > 1:
        etrack_user_id = sys.argv[1]
        live_ok = test_live_euserls(etrack_user_id)
        email_ok = test_email_only(etrack_user_id)
    else:
        print("\n" + "=" * 60)
        print("LIVE TESTING SKIPPED")
        print("=" * 60)
        print("To test with a real etrack user:")
        print("  python3 test_euserls.py <etrack_user_id>")
        print("\nExample:")
        print("  python3 test_euserls.py john_doe")
        live_ok = None
        email_ok = None

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Parsing test: {'✓ PASS' if parsing_ok else '✗ FAIL'}")
    if live_ok is not None:
        print(f"Live test: {'✓ PASS' if live_ok else '✗ FAIL'}")
        print(f"Email test: {'✓ PASS' if email_ok else '✗ FAIL'}")

    print("\nNOTE: For live testing, ensure one of:")
    print("  1. euserls command is in your PATH")
    print("  2. RMTCMD_HOST environment variable is set")
    print(f"     Current RMTCMD_HOST: {os.environ.get('RMTCMD_HOST', '(not set)')}")


if __name__ == "__main__":
    main()
