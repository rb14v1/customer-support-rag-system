# ---------------------------------------------------------------------------
# Automated database-backup Container App Job
#
# Satisfies the rel.backup_configured compliance requirement:
#   - Automated daily backup via Azure Container App Job (cron schedule)
#   - 30-day minimum retention enforced in backup_sqlite_database()
#   - Backups stored in a separate storage account / region from the
#     primary document container (AZURE_BACKUP_STORAGE_CONNECTION_STRING)
#   - Point-in-time recovery: each backup blob is a timestamped SQLite
#     snapshot; restore via `python manage.py backup_db --restore <blob>`
#
# Inputs required at plan/apply time
# -----------------------------------
#   backup_api_image               : Docker image for the API (e.g. from ACR)
#   backup_container_app_env_id    : Resource ID of the Container App Environment
#   backup_storage_connection_string : Connection string for the SEPARATE backup
#                                    storage account (different region from primary)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------

variable "backup_api_image" {
  description = "Docker image (registry/repo:tag) for the API service, used by the backup job."
  type        = string
}

variable "backup_container_app_env_id" {
  description = "Resource ID of the Azure Container App Environment where the backup job will run."
  type        = string
}

variable "backup_storage_connection_string" {
  description = <<-EOT
    Azure Storage connection string for the BACKUP storage account.
    This account MUST reside in a different region from the primary storage
    account to satisfy the cross-region isolation requirement.
  EOT
  type      = string
  sensitive = true
}

variable "backup_container_name" {
  description = "Blob container name inside the backup storage account that holds backup blobs."
  type        = string
  default     = "db-backups"
}

variable "backup_cron_expression" {
  description = "UTC cron expression for the daily backup schedule. Default: every day at 02:00 UTC."
  type        = string
  default     = "0 2 * * *"
}

variable "backup_retention_days" {
  description = "Number of days to retain backup blobs (minimum: 30)."
  type        = number
  default     = 30

  validation {
    condition     = var.backup_retention_days >= 30
    error_message = "backup_retention_days must be at least 30 to satisfy the compliance requirement."
  }
}

variable "backup_db_path" {
  description = "Filesystem path to the SQLite database file inside the container."
  type        = string
  default     = "/app/db.sqlite3"
}

variable "backup_resource_group_name" {
  description = "Name of the Azure Resource Group where the backup job will be created."
  type        = string
}

variable "backup_location" {
  description = "Azure region for the backup job resource (should match the Container App Environment region)."
  type        = string
}

# ---------------------------------------------------------------------------
# Container App Job — scheduled daily backup
# ---------------------------------------------------------------------------

resource "azurerm_container_app_job" "db_backup" {
  name                         = "db-backup-job"
  resource_group_name          = var.backup_resource_group_name
  location                     = var.backup_location
  container_app_environment_id = var.backup_container_app_env_id

  # Allow up to 5 minutes for the backup + prune operation.
  replica_timeout_in_seconds = 300
  # Retry once on transient failures (e.g. network blip during upload).
  replica_retry_limit = 1

  schedule_trigger_config {
    # Run once per day at the configured time.
    cron_expression          = var.backup_cron_expression
    parallelism              = 1
    replica_completion_count = 1
  }

  template {
    container {
      name  = "db-backup"
      image = var.backup_api_image

      # Minimal resources — backup is I/O-bound, not CPU-bound.
      cpu    = 0.25
      memory = "0.5Gi"

      # Invoke the Django management command created in
      # api/management/commands/backup_db.py
      command = ["python", "manage.py", "backup_db"]

      env {
        name  = "DJANGO_SETTINGS_MODULE"
        value = "customer_support.settings"
      }
      env {
        name  = "AZURE_BACKUP_STORAGE_CONNECTION_STRING"
        value = var.backup_storage_connection_string
      }
      env {
        name  = "AZURE_BACKUP_CONTAINER_NAME"
        value = var.backup_container_name
      }
      env {
        name  = "DB_BACKUP_RETENTION_DAYS"
        value = tostring(var.backup_retention_days)
      }
      env {
        name  = "DB_PATH"
        value = var.backup_db_path
      }
    }
  }

  tags = local.default_tags
}
