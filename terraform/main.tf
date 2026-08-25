terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}

  # default_tags propagates tenantId, submissionId, and costCentre to all
  # child resources automatically, satisfying the finops.resources_tagged
  # compliance requirement.
  default_tags {
    tags = local.required_tags
  }
}

locals {
  required_tags = {
    tenantId     = var.tenant_id
    submissionId = var.submission_id
    costCentre   = var.cost_centre
  }
}

resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.required_tags
}
