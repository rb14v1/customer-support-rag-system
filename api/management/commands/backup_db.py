"""
Django management command: backup_db

Usage
-----
Back up the database::

    python manage.py backup_db

Back up with a custom retention period::

    python manage.py backup_db --retention-days 60

Restore from a specific backup blob::

    python manage.py backup_db --restore db.sqlite3.20260101T120000Z.bak

This command is intended to be invoked:
- Manually by operators during incidents.
- Automatically by the scheduled ``db-backup-job`` Azure Container App Job
  defined in ``infra/backup.tf`` (runs daily at 02:00 UTC).

Restore procedure
-----------------
1. Identify the target blob name via the Azure Portal or::

       az storage blob list \\
         --connection-string "$AZURE_BACKUP_STORAGE_CONNECTION_STRING" \\
         --container-name "${AZURE_BACKUP_CONTAINER_NAME:-db-backups}" \\
         --output table

2. Stop the Django application server to prevent writes during restore.
3. Run: ``python manage.py backup_db --restore <blob_name>``
4. Verify: ``python manage.py check --database default``
5. Restart the application server.
"""
import logging
import os

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Back up the SQLite database to the Azure Blob Storage backup account. "
        "Pass --restore <blob_name> to restore a previous backup instead."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--restore",
            metavar="BLOB_NAME",
            default=None,
            help=(
                "Restore the database from the named backup blob "
                "(e.g. db.sqlite3.20260101T120000Z.bak) instead of "
                "creating a new backup."
            ),
        )
        parser.add_argument(
            "--retention-days",
            type=int,
            default=None,
            dest="retention_days",
            help=(
                "Override the backup retention period in days "
                "(minimum enforced: 30). Defaults to the "
                "DB_BACKUP_RETENTION_DAYS environment variable or 30."
            ),
        )

    def handle(self, *args, **options):
        restore_blob = options.get("restore")
        retention_days = options.get("retention_days")

        if restore_blob:
            self._restore(restore_blob)
        else:
            self._backup(retention_days=retention_days)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _backup(self, retention_days=None):
        """Create a new database backup and prune old blobs."""
        from azure_services.blob_service import backup_sqlite_database

        self.stdout.write("Starting database backup …")
        logger.info("backup_db management command: starting backup")

        try:
            blob_name = backup_sqlite_database(retention_days=retention_days)
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            logger.exception("Database backup failed")
            raise CommandError(f"Database backup failed: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Database backup complete. Blob: {blob_name}"
            )
        )
        logger.info("backup_db management command: backup complete, blob=%s", blob_name)

    def _restore(self, blob_name):
        """Restore the database from a named backup blob."""
        from azure_services.blob_service import restore_sqlite_database

        db_path = os.getenv("DB_PATH", "db.sqlite3")

        self.stdout.write(
            f"Restoring database from blob {blob_name!r} to {db_path!r} …"
        )
        self.stdout.write(
            self.style.WARNING(
                "Ensure the application server is stopped before restoring "
                "to avoid data corruption."
            )
        )
        logger.info(
            "backup_db management command: starting restore, blob=%s, target=%s",
            blob_name,
            db_path,
        )

        try:
            restore_sqlite_database(blob_name, db_path)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            logger.exception("Database restore failed")
            raise CommandError(f"Database restore failed: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Database restored successfully from blob '{blob_name}' to '{db_path}'.\n"
                "Next steps:\n"
                "  1. Run: python manage.py check --database default\n"
                "  2. Restart the application server."
            )
        )
        logger.info(
            "backup_db management command: restore complete, blob=%s, target=%s",
            blob_name,
            db_path,
        )
