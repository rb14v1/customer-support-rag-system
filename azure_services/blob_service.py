import datetime
import logging
import os
import shutil

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DATABASE BACKUP
# ---------------------------------------------------------------------------

def backup_sqlite_database(backup_connection_string=None, backup_container=None, db_path=None, retention_days=None):
    """
    Back up the SQLite database file to a dedicated Azure Blob Storage
    container (which should reside in a **different region** from the
    primary document container) and prune blobs that are older than
    ``retention_days`` (minimum 30).

    Blob naming convention:
        db-backups/db.sqlite3.<ISO-8601-UTC-timestamp>.bak

    This function is intended to be called:
    - From the Django management command ``python manage.py backup_db``
    - From an external scheduler (cron, Azure Functions timer, etc.) that
      invokes ``python manage.py backup_db`` on a daily schedule.

    Parameters
    ----------
    backup_connection_string : str, optional
        Azure Storage connection string for the **backup** account.
        Defaults to the ``AZURE_BACKUP_STORAGE_CONNECTION_STRING``
        environment variable (falls back to
        ``AZURE_STORAGE_CONNECTION_STRING`` for local dev).
    backup_container : str, optional
        Blob container name inside the backup storage account.
        Defaults to ``AZURE_BACKUP_CONTAINER_NAME`` env var or
        ``"db-backups"``.
    db_path : str or Path, optional
        Filesystem path to the SQLite database file.
        Defaults to ``DB_PATH`` env var or ``"db.sqlite3"`` relative to
        the current working directory.
    retention_days : int, optional
        Number of days to retain backup blobs (minimum enforced: 30).
        Defaults to ``DB_BACKUP_RETENTION_DAYS`` env var or 30.

    Returns
    -------
    str
        The blob name of the newly created backup.

    Raises
    ------
    FileNotFoundError
        If the SQLite database file does not exist at the given path.
    ValueError
        If required configuration values are missing.
    Exception
        Propagated from the Azure Storage SDK on upload/list/delete errors.
    """
    from azure.storage.blob import BlobServiceClient

    # ------------------------------------------------------------------ cfg
    if backup_connection_string is None:
        backup_connection_string = os.getenv(
            "AZURE_BACKUP_STORAGE_CONNECTION_STRING",
            os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
        )
    if not backup_connection_string:
        raise ValueError(
            "AZURE_BACKUP_STORAGE_CONNECTION_STRING (or "
            "AZURE_STORAGE_CONNECTION_STRING) must be set."
        )

    if backup_container is None:
        backup_container = os.getenv("AZURE_BACKUP_CONTAINER_NAME", "db-backups")

    if db_path is None:
        db_path = os.getenv("DB_PATH", "db.sqlite3")

    if retention_days is None:
        try:
            retention_days = int(os.getenv("DB_BACKUP_RETENTION_DAYS", "30"))
        except (ValueError, TypeError):
            retention_days = 30
    retention_days = max(30, retention_days)  # enforce minimum

    # ----------------------------------------------------------- validate db
    if not os.path.isfile(db_path):
        raise FileNotFoundError(
            f"SQLite database not found at path: {db_path!r}"
        )

    # ------------------------------------------------------ create temp copy
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    db_filename = os.path.basename(db_path)
    blob_name = f"{db_filename}.{timestamp}.bak"
    tmp_copy = f"{db_path}.{timestamp}.tmp"

    logger.info(
        "Starting database backup: source=%s, blob=%s, container=%s",
        db_path,
        blob_name,
        backup_container,
    )

    shutil.copy2(db_path, tmp_copy)
    logger.info("Temporary copy created at %s", tmp_copy)

    # ---------------------------------------------------------------- upload
    try:
        service_client = BlobServiceClient.from_connection_string(
            backup_connection_string
        )
        container_client = service_client.get_container_client(backup_container)

        # Ensure container exists (idempotent).
        try:
            container_client.create_container()
            logger.info("Created backup container '%s'", backup_container)
        except Exception:
            pass  # container already exists

        with open(tmp_copy, "rb") as data:
            container_client.upload_blob(
                name=blob_name,
                data=data,
                overwrite=True,
            )
        logger.info("Uploaded backup blob '%s' to container '%s'", blob_name, backup_container)

    finally:
        # Remove the temporary copy regardless of upload outcome.
        try:
            os.remove(tmp_copy)
        except OSError:
            pass

    # -------------------------------------------------------- prune old blobs
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=retention_days)
    logger.info(
        "Pruning backup blobs older than %d days (before %s)",
        retention_days,
        cutoff.isoformat(),
    )

    deleted_count = 0
    try:
        for blob in container_client.list_blobs():
            last_modified = blob.last_modified
            if last_modified is not None:
                # Make offset-naive for comparison if necessary.
                if hasattr(last_modified, "tzinfo") and last_modified.tzinfo is not None:
                    last_modified = last_modified.replace(tzinfo=None)
                if last_modified < cutoff:
                    container_client.delete_blob(blob.name)
                    logger.info("Deleted old backup blob '%s'", blob.name)
                    deleted_count += 1
    except Exception:
        logger.exception("Error during backup retention pruning (non-fatal)")

    logger.info(
        "Database backup complete: blob=%s, pruned=%d old blobs",
        blob_name,
        deleted_count,
    )
    return blob_name


def restore_sqlite_database(blob_name, restore_path, backup_connection_string=None, backup_container=None):
    """
    Restore a SQLite database from a backup blob stored in Azure Blob Storage.

    **Restore procedure** (also documented in docs/database-backup.md):

    1. Identify the target backup blob name (e.g.
       ``db.sqlite3.20260101T120000Z.bak``) using the Azure Portal or
       ``az storage blob list``.
    2. Stop the Django application server to prevent writes during restore.
    3. Call this function (or the management command
       ``python manage.py backup_db --restore <blob_name>``).
    4. Verify the restored database with
       ``python manage.py check --database default``.
    5. Restart the application server.

    Parameters
    ----------
    blob_name : str
        Name of the blob to restore (e.g.
        ``"db.sqlite3.20260101T120000Z.bak"``).
    restore_path : str or Path
        Local filesystem path where the restored database file should be
        written (e.g. ``"db.sqlite3"``).
    backup_connection_string : str, optional
        Azure Storage connection string for the backup account.
    backup_container : str, optional
        Blob container name.  Defaults to ``AZURE_BACKUP_CONTAINER_NAME``
        env var or ``"db-backups"``.

    Raises
    ------
    ValueError
        If required configuration values are missing.
    Exception
        Propagated from the Azure Storage SDK.
    """
    from azure.storage.blob import BlobServiceClient

    if backup_connection_string is None:
        backup_connection_string = os.getenv(
            "AZURE_BACKUP_STORAGE_CONNECTION_STRING",
            os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
        )
    if not backup_connection_string:
        raise ValueError(
            "AZURE_BACKUP_STORAGE_CONNECTION_STRING must be set."
        )

    if backup_container is None:
        backup_container = os.getenv("AZURE_BACKUP_CONTAINER_NAME", "db-backups")

    logger.info(
        "Starting database restore: blob=%s, target=%s, container=%s",
        blob_name,
        restore_path,
        backup_container,
    )

    service_client = BlobServiceClient.from_connection_string(backup_connection_string)
    container_client = service_client.get_container_client(backup_container)
    blob_client = container_client.get_blob_client(blob_name)

    with open(restore_path, "wb") as f:
        f.write(blob_client.download_blob().readall())

    logger.info(
        "Database restore complete: blob=%s written to %s",
        blob_name,
        restore_path,
    )


def upload_blob(container_client, file_path, blob_name):
    """Upload a file to Azure Blob Storage."""
    logger.info("Starting upload_blob for file '%s' as blob '%s'", file_path, blob_name)
    try:
        with open(file_path, "rb") as data:
            container_client.upload_blob(
                name=blob_name,
                data=data,
                overwrite=True,
            )

        logger.info(
            "Finished upload_blob successfully for blob '%s'",
            blob_name,
        )

    except FileNotFoundError:
        logger.error(
            "File not found: %s",
            file_path,
        )
        raise

    except Exception:
        logger.exception(
            "Failed to upload blob '%s'",
            blob_name,
        )
        raise


def download_blob(container_client, blob_name, download_path):
    """Download a blob to a local file."""
    logger.info("Starting download_blob for blob '%s' to '%s'", blob_name, download_path)
    try:
        blob_client = container_client.get_blob_client(
            blob_name
        )

        with open(download_path, "wb") as file:
            file.write(
                blob_client.download_blob().readall()
            )

        logger.info(
            "Finished download_blob successfully for blob '%s'",
            blob_name,
        )

    except Exception:
        logger.exception(
            "Failed to download blob '%s'",
            blob_name,
        )
        raise


def list_blobs(container_client):
    """List blobs in the configured container."""
    logger.info("Starting list_blobs")
    try:
        blobs = list(container_client.list_blobs())

        logger.info(
            "Finished list_blobs successfully (found %d blobs)",
            len(blobs),
        )

        return blobs

    except Exception:
        logger.exception("Failed to list blobs")
        raise


def delete_blob(container_client, blob_name):
    """Delete a blob from Azure Blob Storage."""
    logger.info("Starting delete_blob for blob '%s'", blob_name)
    try:
        blob_client = container_client.get_blob_client(
            blob_name
        )

        blob_client.delete_blob()

        logger.info(
            "Finished delete_blob successfully for blob '%s'",
            blob_name,
        )

    except Exception:
        logger.exception(
            "Failed to delete blob '%s'",
            blob_name,
        )
        raise