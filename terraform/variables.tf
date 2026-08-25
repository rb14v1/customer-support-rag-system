variable "tenant_id" {
  description = "The tenantId used for cost allocation and resource attribution."
  type        = string
}

variable "submission_id" {
  description = "The submissionId used for cost allocation and incident attribution."
  type        = string
}

variable "cost_centre" {
  description = "The costCentre used for cost allocation and automated governance."
  type        = string
}

variable "location" {
  description = "Azure region where resources are deployed."
  type        = string
  default     = "eastus"
}

variable "resource_group_name" {
  description = "Name of the Azure resource group."
  type        = string
  default     = "customer-support-system-rg"
}
