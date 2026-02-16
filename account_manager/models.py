"""
Database models and core account management functionality
"""

import sqlite3
import time
from typing import Optional, Dict, List, Any

# Database lock retry settings
DB_LOCK_RETRIES = 5
DB_LOCK_DELAY = 0.5  # seconds


class DatabaseLockedError(Exception):
    """Raised when database remains locked after retries"""
    pass


def retry_on_lock(func):
    """Decorator to retry database operations on lock"""
    def wrapper(*args, **kwargs):
        last_error = None
        for attempt in range(DB_LOCK_RETRIES):
            try:
                return func(*args, **kwargs)
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    last_error = e
                    if attempt < DB_LOCK_RETRIES - 1:
                        time.sleep(DB_LOCK_DELAY * (attempt + 1))
                        continue
                raise
        raise DatabaseLockedError(
            f"Database remained locked after {DB_LOCK_RETRIES} retries. "
            "Another process may be using the database. Try again later."
        ) from last_error
    return wrapper


class AccountManager:
    """Manages employee accounts across different platforms"""

    def __init__(self, db_path: str = "accounts.db"):
        """
        Initialize the Account Manager

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._connect()
        self._create_table()

    def _connect(self):
        """Establish database connection with timeout for lock handling"""
        self.conn = sqlite3.connect(self.db_path, timeout=30.0)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        self.cursor = self.conn.cursor()

    def _create_table(self):
        """Create the accounts table if it doesn't exist"""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                etrack_user_id TEXT UNIQUE NOT NULL,
                first_name TEXT,
                last_name TEXT,
                veritas_email TEXT,
                cohesity_email TEXT,
                community_account TEXT,
                jira_account TEXT,
                manual_verified TEXT DEFAULT 'no',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for faster lookups
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_etrack_user
            ON accounts(etrack_user_id)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_veritas_email
            ON accounts(veritas_email)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cohesity_email
            ON accounts(cohesity_email)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jira
            ON accounts(jira_account)
        """)

        # Create action_log table to track all script actions
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                target_type TEXT,
                target_id TEXT,
                old_value TEXT,
                new_value TEXT,
                status TEXT DEFAULT 'success',
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Index for querying action logs
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_action_type
            ON action_log(action_type)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_action_created
            ON action_log(created_at)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_action_target
            ON action_log(target_type, target_id)
        """)

        self.conn.commit()

    @retry_on_lock
    def add_account(self, etrack_user_id: str, first_name: str = None,
                   last_name: str = None, veritas_email: str = None,
                   cohesity_email: str = None, community_account: str = None,
                   jira_account: str = None, manual_verified: str = 'no',
                   notes: str = None) -> int:
        """
        Add a new account record

        Args:
            etrack_user_id: Etrack User ID (required, must be unique)
            first_name: First name
            last_name: Last name
            veritas_email: Veritas email address
            cohesity_email: Cohesity email address
            community_account: Community account name
            jira_account: Jira account name
            manual_verified: Manual verification status ('yes' or 'no', default: 'no')
            notes: Additional notes (multi-line text)

        Returns:
            ID of the newly created record
        """
        try:
            self.cursor.execute("""
                INSERT INTO accounts
                (etrack_user_id, first_name, last_name, veritas_email, cohesity_email,
                 community_account, jira_account, manual_verified, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (etrack_user_id, first_name, last_name, veritas_email, cohesity_email,
                  community_account, jira_account, manual_verified, notes))

            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Account with etrack_user_id '{etrack_user_id}' already exists") from e

    @retry_on_lock
    def update_account(self, etrack_user_id: str, **kwargs) -> bool:
        """
        Update an existing account record

        Args:
            etrack_user_id: Etrack User ID to identify the record
            **kwargs: Fields to update (first_name, last_name, veritas_email, cohesity_email,
                     community_account, jira_account, manual_verified, notes)

        Returns:
            True if update successful, False if record not found
        """
        allowed_fields = ['first_name', 'last_name', 'veritas_email', 'cohesity_email',
                         'community_account', 'jira_account', 'manual_verified', 'notes']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        # Build UPDATE query dynamically
        set_clause = ", ".join([f"{field} = ?" for field in updates.keys()])
        set_clause += ", updated_at = CURRENT_TIMESTAMP"
        values = list(updates.values()) + [etrack_user_id]

        self.cursor.execute(f"""
            UPDATE accounts
            SET {set_clause}
            WHERE etrack_user_id = ?
        """, values)

        self.conn.commit()
        return self.cursor.rowcount > 0

    @retry_on_lock
    def delete_account(self, etrack_user_id: str) -> bool:
        """
        Delete an account record

        Args:
            etrack_user_id: Etrack User ID to identify the record

        Returns:
            True if deletion successful, False if record not found
        """
        self.cursor.execute("DELETE FROM accounts WHERE etrack_user_id = ?", (etrack_user_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def get_account(self, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Get a single account by any field

        Args:
            **kwargs: Field to search by (e.g., etrack_user_id='ET12345', jira_account='john.doe')

        Returns:
            Dictionary containing account information or None if not found
        """
        if not kwargs or len(kwargs) != 1:
            raise ValueError("Provide exactly one search parameter")

        field, value = list(kwargs.items())[0]
        allowed_fields = ['id', 'etrack_user_id', 'veritas_email', 'cohesity_email',
                         'community_account', 'jira_account']

        if field not in allowed_fields:
            raise ValueError(f"Invalid field: {field}")

        self.cursor.execute(f"SELECT * FROM accounts WHERE {field} = ?", (value,))
        row = self.cursor.fetchone()

        return dict(row) if row else None

    def search_accounts(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Search accounts with partial matching

        Args:
            **kwargs: Fields to search (supports LIKE queries)

        Returns:
            List of matching account dictionaries
        """
        if not kwargs:
            # Return all accounts if no search criteria
            self.cursor.execute("SELECT * FROM accounts ORDER BY etrack_user_id")
            return [dict(row) for row in self.cursor.fetchall()]

        conditions = []
        values = []

        for field, value in kwargs.items():
            conditions.append(f"{field} LIKE ?")
            values.append(f"%{value}%")

        query = f"SELECT * FROM accounts WHERE {' AND '.join(conditions)} ORDER BY etrack_user_id"
        self.cursor.execute(query, values)

        return [dict(row) for row in self.cursor.fetchall()]

    def translate(self, identifier: str, return_field: str) -> Optional[str]:
        """
        Translate from any identifier to requested field

        Args:
            identifier: Any identifier (etrack_user_id, email, jira_account, etc.)
            return_field: Field to return (e.g., 'jira_account', 'veritas_email')

        Returns:
            Value of the requested field or None if not found

        Examples:
            translate('ET12345', 'jira_account')  -> 'john.doe'
            translate('john@vcompany.com', 'cohesity_email')  -> 'john@ccompany.com'
        """
        allowed_fields = ['etrack_user_id', 'veritas_email', 'cohesity_email',
                         'community_account', 'jira_account']

        if return_field not in allowed_fields:
            raise ValueError(f"Invalid return field: {return_field}")

        # Try to find the record by searching all fields
        search_fields = ['etrack_user_id', 'veritas_email', 'cohesity_email',
                        'community_account', 'jira_account']

        for field in search_fields:
            self.cursor.execute(f"SELECT {return_field} FROM accounts WHERE {field} = ?",
                              (identifier,))
            result = self.cursor.fetchone()
            if result and result[0]:
                return result[0]

        return None

    def get_all_accounts(self) -> List[Dict[str, Any]]:
        """
        Get all accounts

        Returns:
            List of all account dictionaries
        """
        self.cursor.execute("SELECT * FROM accounts ORDER BY etrack_user_id")
        return [dict(row) for row in self.cursor.fetchall()]

    @retry_on_lock
    def log_action(self, action_type: str, target_type: str = None,
                   target_id: str = None, old_value: str = None,
                   new_value: str = None, status: str = 'success',
                   details: str = None) -> int:
        """
        Log an action taken by the script

        Args:
            action_type: Type of action (e.g., 'add_account', 'update_account',
                        'assign_fi', 'assign_etrack', 'fix_fi', 'verify_account')
            target_type: Type of target (e.g., 'account', 'fi', 'etrack')
            target_id: ID of target (e.g., etrack_user_id, FI-12345, 12345678)
            old_value: Previous value (for updates)
            new_value: New value (for updates)
            status: Status of action ('success', 'failed', 'skipped', 'dry_run')
            details: Additional details or error message

        Returns:
            ID of the log entry
        """
        self.cursor.execute("""
            INSERT INTO action_log
            (action_type, target_type, target_id, old_value, new_value, status, details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (action_type, target_type, target_id, old_value, new_value, status, details))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_action_log(self, limit: int = 50, action_type: str = None,
                       target_type: str = None, target_id: str = None,
                       status: str = None, since: str = None) -> List[Dict[str, Any]]:
        """
        Get action log entries with optional filtering

        Args:
            limit: Maximum number of entries to return (default 50)
            action_type: Filter by action type
            target_type: Filter by target type
            target_id: Filter by target ID
            status: Filter by status
            since: Filter by date (YYYY-MM-DD format, entries on or after)

        Returns:
            List of action log entries (most recent first)
        """
        query = "SELECT * FROM action_log WHERE 1=1"
        params = []

        if action_type:
            query += " AND action_type = ?"
            params.append(action_type)
        if target_type:
            query += " AND target_type = ?"
            params.append(target_type)
        if target_id:
            query += " AND target_id = ?"
            params.append(target_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        if since:
            query += " AND date(created_at) >= date(?)"
            params.append(since)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        self.cursor.execute(query, params)
        return [dict(row) for row in self.cursor.fetchall()]

    def get_action_summary(self, since: str = None) -> Dict[str, Dict[str, int]]:
        """
        Get summary statistics of actions

        Args:
            since: Filter by date (YYYY-MM-DD format, entries on or after)

        Returns:
            Dictionary with action_type -> {status -> count}
        """
        query = """
            SELECT action_type, status, COUNT(*) as count
            FROM action_log
            WHERE 1=1
        """
        params = []

        if since:
            query += " AND date(created_at) >= date(?)"
            params.append(since)

        query += " GROUP BY action_type, status ORDER BY action_type, status"

        self.cursor.execute(query, params)

        summary = {}
        for row in self.cursor.fetchall():
            action_type = row['action_type']
            status = row['status']
            count = row['count']
            if action_type not in summary:
                summary[action_type] = {}
            summary[action_type][status] = count

        return summary

    def clear_action_log(self, before: str = None) -> int:
        """
        Clear action log entries

        Args:
            before: Clear entries before this date (YYYY-MM-DD), or all if None

        Returns:
            Number of entries deleted
        """
        if before:
            self.cursor.execute(
                "DELETE FROM action_log WHERE date(created_at) < date(?)",
                (before,)
            )
        else:
            self.cursor.execute("DELETE FROM action_log")

        deleted = self.cursor.rowcount
        self.conn.commit()
        return deleted

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
