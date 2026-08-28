terraform {
  required_version = ">= 1.5"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

# ---------------------------------------------------------------------------
# Mandatory FinOps tags
# Reference local.default_tags (or merge with it) on every resource block so
# that tenantId, submissionId, and costCentre are always present.
#
# Example:
#   resource "azurerm_storage_account" "docs" {
#     ...
#     tags = local.default_tags
#   }
#
# To add resource-specific tags while keeping the mandatory ones:
#   tags = merge(local.default_tags, { environment = "production" })
# ---------------------------------------------------------------------------

locals {
  default_tags = {
    tenantId     = var.tenant_id
    submissionId = var.submission_id
    costCentre   = var.cost_centre
  }
}
