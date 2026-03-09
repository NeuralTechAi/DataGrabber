"""
Database migration script for DataGrabber (PostgreSQL version)
This script sets up the initial database schema and creates the necessary tables.
Run this script to ensure your database is up to date with all schema changes.
IMPORTANT: For existing databases with data in the 'data' column of data_record table,
run the standalone migration script first: python migrate_remove_data_column.py
"""
import os
import sys
import psycopg2
from psycopg2 import sql

# Add the parent directory to the path so we can import from app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app
from app.extensions import db
from app.models import User, Admin, Project, Document, DataRecord, AdminActivity, PasswordResetToken, ProcessingJob, UserAISettings

def run_migrations():
    """Run database migrations"""
    print("🚀 Running DataGrabber Database Migrations (PostgreSQL)")
    print("=" * 50)

    # Create app using factory
    app = create_app('development')

    with app.app_context():
        try:
            # Ensure all tables exist
            print("About to create all tables...")
            db.create_all()
            print("Database schema created successfully.")

            # Use PostgreSQL-compatible queries
            engine = db.engine
            conn = engine.raw_connection()
            cursor = conn.cursor()

            # --- Custom migration for is_suspended ---
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'user';
            """)
            user_columns = [row[0] for row in cursor.fetchall()]

            if "is_suspended" not in user_columns:
                print("Adding missing column 'is_suspended' to user table...")
                cursor.execute(sql.SQL("ALTER TABLE {} ADD COLUMN is_suspended BOOLEAN DEFAULT FALSE;").format(sql.Identifier('user')))
                conn.commit()
                print("Column 'is_suspended' added successfully.")
            else:
                print("Column 'is_suspended' already exists.")

            # --- Custom migration for AdminActivity ---
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'admin_activity';
            """)
            activity_columns = [row[0] for row in cursor.fetchall()]

            # Remove target_user_id if exists (PostgreSQL requires recreating the table to drop a column)
            if "target_user_id" in activity_columns:
                print("Dropping column 'target_user_id' from admin_activity...")
                print("PostgreSQL requires table recreation to drop columns. Skipping automatic drop.")

            # Add target_user_email if missing
            if "target_user_email" not in activity_columns:
                print("Adding column 'target_user_email' to admin_activity...")
                cursor.execute(sql.SQL("ALTER TABLE {} ADD COLUMN target_user_email VARCHAR(120);").format(sql.Identifier('admin_activity')))
                conn.commit()
                print("Column 'target_user_email' added successfully.")
            else:
                print("Column 'target_user_email' already exists.")

            # --- Custom migration for PasswordResetToken table ---
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'password_reset_token';
            """)
            password_reset_table_exists = cursor.fetchone() is not None

            if not password_reset_table_exists:
                print("Creating password_reset_token table...")
                cursor.execute('''
                    CREATE TABLE password_reset_token (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        token VARCHAR(255) NOT NULL UNIQUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL,
                        used BOOLEAN DEFAULT FALSE,
                        FOREIGN KEY (user_id) REFERENCES "user"(id)
                    );
                ''')

                # Create index on token for faster lookups
                cursor.execute('CREATE INDEX ix_password_reset_token_token ON password_reset_token (token);')

                # Create index on user_id for faster lookups
                cursor.execute('CREATE INDEX ix_password_reset_token_user_id ON password_reset_token (user_id);')

                conn.commit()
                print("Table 'password_reset_token' created successfully.")
            else:
                print("Table 'password_reset_token' already exists.")

                # Check if all required columns exist
                cursor.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'password_reset_token';
                """)
                reset_columns = [row[0] for row in cursor.fetchall()]

                required_columns = ['id', 'user_id', 'token', 'created_at', 'expires_at', 'used']
                missing_columns = []

                for col in required_columns:
                    if col not in reset_columns:
                        missing_columns.append(col)

                if missing_columns:
                    print(f"Adding missing columns to password_reset_token: {', '.join(missing_columns)}")
                    for col in missing_columns:
                        if col == 'user_id':
                            cursor.execute(sql.SQL("ALTER TABLE {} ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0;").format(sql.Identifier('password_reset_token')))
                        elif col == 'token':
                            cursor.execute(sql.SQL("ALTER TABLE {} ADD COLUMN token VARCHAR(255) NOT NULL DEFAULT '';").format(sql.Identifier('password_reset_token')))
                        elif col == 'created_at':
                            cursor.execute(sql.SQL("ALTER TABLE {} ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;").format(sql.Identifier('password_reset_token')))
                        elif col == 'expires_at':
                            cursor.execute(sql.SQL("ALTER TABLE {} ADD COLUMN expires_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;").format(sql.Identifier('password_reset_token')))
                        elif col == 'used':
                            cursor.execute(sql.SQL("ALTER TABLE {} ADD COLUMN used BOOLEAN DEFAULT FALSE;").format(sql.Identifier('password_reset_token')))
                    conn.commit()
                    print("Missing columns added successfully.")

            # --- Custom migration for Document table columns ---
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'document';
            """)
            document_columns = [row[0] for row in cursor.fetchall()]

            # Check if document table exists and add missing columns
            if "file_path" in document_columns:
                print("Document table file_path column already exists.")
            else:
                print("Warning: Document table or file_path column not found. Database may need recreation.")

            # Add 'processed' column if missing
            if "processed" not in document_columns:
                print("Adding 'processed' column to document table...")
                cursor.execute(sql.SQL("ALTER TABLE {} ADD COLUMN processed BOOLEAN DEFAULT FALSE;").format(sql.Identifier('document')))

                # Update existing records: mark as processed if they have data_records
                cursor.execute("""
                    UPDATE document
                    SET processed = TRUE
                    WHERE id IN (
                        SELECT DISTINCT document_id
                        FROM data_record
                    );
                """)

                conn.commit()
                print("Column 'processed' added and existing processed documents updated.")
            else:
                print("Column 'processed' already exists.")

            # --- Custom migration for DataRecord table (data column removal) ---
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'data_record';
            """)
            data_record_columns = [row[0] for row in cursor.fetchall()]

            # Check if old 'data' column exists - if so, migration is needed
            if "data" in data_record_columns:
                print("Found old 'data' column in data_record table. Migration needed...")
                print("WARNING: This migration will remove the 'data' column and switch to file-based storage.")
                print("Please run the standalone migration script: migrate_remove_data_column.py")
                print("This migration will:")
                print("  - Export existing data to Excel files")
                print("  - Remove the 'data' column")
                print("  - Add 'data_file_path' and 'row_index' columns")
            else:
                print("DataRecord table already uses file-based storage (no 'data' column found).")

                # Ensure new columns exist
                required_columns = ["data_file_path", "row_index"]
                missing_columns = []

                for col in required_columns:
                    if col not in data_record_columns:
                        missing_columns.append(col)

                if missing_columns:
                    print(f"Adding missing file-based storage columns: {', '.join(missing_columns)}")
                    for col in missing_columns:
                        if col == "data_file_path":
                            cursor.execute(sql.SQL("ALTER TABLE {} ADD COLUMN data_file_path VARCHAR(512);").format(sql.Identifier('data_record')))
                        elif col == "row_index":
                            cursor.execute(sql.SQL("ALTER TABLE {} ADD COLUMN row_index INTEGER;").format(sql.Identifier('data_record')))
                    conn.commit()
                    print("File-based storage columns added successfully.")

            # Clean up any expired password reset tokens
            try:
                cursor.execute("DELETE FROM password_reset_token WHERE expires_at < NOW();")
                deleted_count = cursor.rowcount
                conn.commit()
                if deleted_count > 0:
                    print(f"Cleaned up {deleted_count} expired password reset tokens.")
                else:
                    print("No expired password reset tokens to clean up.")
            except Exception as e:
                print(f"Warning: Could not clean up expired tokens: {e}")

            # Close cursor and connection
            cursor.close()
            conn.close()

            # Verify tables
            inspector = db.inspect(engine)
            tables = inspector.get_table_names()
            print(f"Current tables: {', '.join(tables)}")
            return True
        except Exception as e:
            print(f"Error running migrations: {e}")
            return False

def check_schema_status():
    """Check the current schema status"""
    print("\nChecking database schema status...")

    app = create_app('development')

    with app.app_context():
        try:
            engine = db.engine
            conn = engine.raw_connection()
            cursor = conn.cursor()

            # Check all tables
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            tables = [row[0] for row in cursor.fetchall()]
            print(f"Current tables: {', '.join(tables)}")

            # Check password_reset_token table specifically
            if 'password_reset_token' in tables:
                cursor.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'password_reset_token';
                """)
                columns = cursor.fetchall()
                print("\nPassword Reset Token table structure:")
                for col in columns:
                    print(f"  - {col[0]} ({col[1]}) {'NOT NULL' if col[2] == 'NO' else 'NULL'}")

                # Check for any existing tokens
                cursor.execute("SELECT COUNT(*) FROM password_reset_token;")
                token_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM password_reset_token WHERE used = FALSE AND expires_at > NOW();")
                active_count = cursor.fetchone()[0]
                print(f"  - Total tokens: {token_count}")
                print(f"  - Active tokens: {active_count}")
            else:
                print("\n❌ Password Reset Token table NOT found!")

            # Check data_record table schema
            if 'data_record' in tables:
                cursor.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'data_record';
                """)
                columns = cursor.fetchall()
                print("\nDataRecord table structure:")
                for col in columns:
                    print(f"  - {col[0]} ({col[1]}) {'NOT NULL' if col[2] == 'NO' else 'NULL'}")

                # Check storage type
                column_names = [col[0] for col in columns]
                if 'data' in column_names:
                    print("  ⚠️  Using old database storage (data column exists)")
                    print("  📋 Run: python migrate_remove_data_column.py")
                elif 'data_file_path' in column_names and 'row_index' in column_names:
                    print("  ✅ Using file-based storage (data_file_path, row_index columns)")
                else:
                    print("  ❌ Incomplete schema - missing file-based storage columns")
            else:
                print("\n❌ DataRecord table NOT found!")

            cursor.close()
            conn.close()

        except Exception as e:
            print(f"Error checking schema: {e}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='DataGrabber Database Migration Tool')
    parser.add_argument('--check', action='store_true', help='Check schema status without running migrations')
    args = parser.parse_args()

    if args.check:
        check_schema_status()
    else:
        print("🚀 Running DataGrabber Database Migrations")
        print("=" * 50)
        success = run_migrations()

        if success:
            print("\n✅ Migration completed successfully!")
            check_schema_status()
        else:
            print("\n❌ Migration failed!")

        sys.exit(0 if success else 1)
