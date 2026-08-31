# ---------------------------------------------------------------------------
# Automated database backup – Azure Automation Account
# ---------------------------------------------------------------------------
# Provisions a daily Python 3 runbook (02:00 UTC) that executes the same
# backup logic as azure_services/blob_service.backup_sqlite_database().
# The runbook reads credentials from encrypted Automation Account variables
# so that no secrets are stored in Terraform state in plain text.
#
# Required Terraform variables (set via tfvars or environment):
#   backup_storage_connection_string  – Azure Storage connection string for
#                                       the backup account (different region
#                                       from the primary storage account).
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Input variables
# ---------------------------------------------------------------------------

variable "backup_storage_connection_string" {
  description = "Azure Storage connection string for the backup account (must be in a different region from the primary account). Maps to AZURE_BACKUP_STORAGE_CONNECTION_STRING."
  type        = string
  sensitive   = true
}

variable "backup_container_name" {
  description = "Blob container name inside the backup storage account that holds SQLite backup blobs."
  type        = string
  default     = "db-backups"
}

variable "backup_retention_days" {
  description = "Number of days of backup blobs to retain (minimum 30)."
  type        = number
  default     = 30

  validation {
    condition     = var.backup_retention_days >= 30
    error_message = "backup_retention_days must be at least 30 to satisfy the backup retention policy."
  }
}

# ---------------------------------------------------------------------------
# Azure Automation Account
# ---------------------------------------------------------------------------

resource "azurerm_automation_account" "backup" {
  name                = "aa-db-backup"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku_name            = "Basic"
  tags                = local.required_tags
}

# ---------------------------------------------------------------------------
# Encrypted runbook variables (connection string is encrypted at rest)
# ---------------------------------------------------------------------------

resource "azurerm_automation_variable_string" "backup_connection_string" {
  name                    = "BackupStorageConnectionString"
  resource_group_name     = azurerm_resource_group.main.name
  automation_account_name = azurerm_automation_account.backup.name
  value                   = var.backup_storage_connection_string
  encrypted               = true
}

resource "azurerm_automation_variable_string" "backup_container_name" {
  name                    = "BackupContainerName"
  resource_group_name     = azurerm_resource_group.main.name
  automation_account_name = azurerm_automation_account.backup.name
  value                   = var.backup_container_name
  encrypted               = false
}

resource "azurerm_automation_variable_int" "backup_retention_days" {
  name                    = "BackupRetentionDays"
  resource_group_name     = azurerm_resource_group.main.name
  automation_account_name = azurerm_automation_account.backup.name
  value                   = var.backup_retention_days
  encrypted               = false
}

# ---------------------------------------------------------------------------
# Python 3 Runbook – daily backup logic
# Mirrors azure_services/blob_service.backup_sqlite_database().
# azure-storage-blob is installed at runtime via pip (standard pattern for
# Azure Automation Python 3 runbooks without a custom package gallery).
# ---------------------------------------------------------------------------

resource "azurerm_automation_runbook" "db_backup" {
  name                    = "db-daily-backup"
  location                = azurerm_resource_group.main.location
  resource_group_name     = azurerm_resource_group.main.name
  automation_account_name = azurerm_automation_account.backup.name
  log_verbose             = false
  log_progress            = true
  runbook_type            = "Python3"
  tags                    = local.required_tags

  # The content block is kept inline so changes are tracked in version control.
  content = <<-PYTHON
    """
    Daily SQLite database backup runbook.

    Mirrors the logic in azure_services/blob_service.backup_sqlite_database().
    Credentials are read from Automation Account encrypted variables so that
    no secrets are embedded in the runbook source.

    Retention: minimum 30 days, driven by the BackupRetentionDays variable.
    """
    import subprocess
    import sys

    # Ensure azure-storage-blob is available in the runbook sandbox.
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--quiet", "azure-storage-blob"],
    )

    import automationassets  # noqa: E402 – Azure Automation built-in
    import datetime
    import logging
    import os
    import shutil

    from azure.storage.blob import BlobServiceClient  # noqa: E402

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger(__name__)


    def run_backup():
        # ---------------------------------------------------------------- cfg
        backup_connection_string = automationassets.get_automation_variable(
            "BackupStorageConnectionString"
        )
        backup_container = automationassets.get_automation_variable(
            "BackupContainerName"
        )
        try:
            retention_days = int(
                automationassets.get_automation_variable("BackupRetentionDays")
            )
        except Exception:
            retention_days = 30
        retention_days = max(30, retention_days)  # enforce minimum

        db_path = os.getenv("DB_PATH", "db.sqlite3")

        # --------------------------------------------------------- validate db
        if not os.path.isfile(db_path):
            logger.error("SQLite database not found at path: %s", db_path)
            raise FileNotFoundError(f"SQLite database not found: {db_path!r}")

        # ---------------------------------------------------- create temp copy
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        db_filename = os.path.basename(db_path)
        blob_name = f"{db_filename}.{timestamp}.bak"
        tmp_copy = f"{db_path}.{timestamp}.tmp"

        logger.info("Starting backup: blob=%s container=%s", blob_name, backup_container)
        shutil.copy2(db_path, tmp_copy)

        # --------------------------------------------------------------- upload
        try:
            service_client = BlobServiceClient.from_connection_string(
                backup_connection_string
            )
            container_client = service_client.get_container_client(backup_container)
            try:
                container_client.create_container()
                logger.info("Created backup container '%s'", backup_container)
            except Exception:
                pass  # container already exists

            with open(tmp_copy, "rb") as data:
                container_client.upload_blob(name=blob_name, data=data, overwrite=True)
            logger.info("Uploaded backup blob '%s'", blob_name)
        finally:
            try:
                os.remove(tmp_copy)
            except OSError:
                pass

        # --------------------------------------------------- prune old blobs
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=retention_days)
        logger.info(
            "Pruning blobs older than %d days (before %s)", retention_days, cutoff.isoformat()
        )
        deleted = 0
        try:
            for blob in container_client.list_blobs():
                lm = blob.last_modified
                if lm is not None:
                    if hasattr(lm, "tzinfo") and lm.tzinfo is not None:
                        lm = lm.replace(tzinfo=None)
                    if lm < cutoff:
                        container_client.delete_blob(blob.name)
                        logger.info("Pruned old blob '%s'", blob.name)
                        deleted += 1
        except Exception:
            logger.exception("Error during retention pruning (non-fatal)")

        logger.info("Backup complete: blob=%s pruned=%d", blob_name, deleted)
        return blob_name


    run_backup()
    PYTHON
}

# ---------------------------------------------------------------------------
# Daily schedule – 02:00 UTC
# start_time is set to the day after initial provisioning; ignore_changes
# prevents Terraform from detecting drift on subsequent plans (Azure
# advances the start_time automatically after each run).
# ---------------------------------------------------------------------------

resource "azurerm_automation_schedule" "daily_02_utc" {
  name                    = "daily-02-utc"
  resource_group_name     = azurerm_resource_group.main.name
  automation_account_name = azurerm_automation_account.backup.name
  frequency               = "Day"
  interval                = 1
  timezone                = "UTC"
  start_time              = "2026-09-01T02:00:00+00:00"
  description             = "Triggers the daily SQLite database backup runbook at 02:00 UTC."

  lifecycle {
    # Azure mutates start_time after each run; ignore to prevent perpetual diff.
    ignore_changes = [start_time]
  }
}

# ---------------------------------------------------------------------------
# Link runbook → schedule
# ---------------------------------------------------------------------------

resource "azurerm_automation_job_schedule" "db_backup_daily" {
  resource_group_name     = azurerm_resource_group.main.name
  automation_account_name = azurerm_automation_account.backup.name
  schedule_name           = azurerm_automation_schedule.daily_02_utc.name
  runbook_name            = azurerm_automation_runbook.db_backup.name
}
