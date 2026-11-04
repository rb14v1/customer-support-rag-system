variable "vnet_id" {
  description = "ID of the one shared, VNet-integrated Container Apps Environment's virtual network."
  type        = string
}

variable "subnet_id" {
  description = "ID of the subnet private endpoints attach to, inside the shared VNet."
  type        = string
}

variable "hub_resource_group" {
  description = "Resource group holding the privatelink DNS zones every app shares. Harbour creates the zones before this runs; this config only links its own VNet into them."
  type        = string
}

variable "mysql_subnet_id" {
  description = "ID of the subnet delegated to Microsoft.DBforMySQL/flexibleServers, inside the shared VNet. Only MySQL uses it."
  type        = string
  default     = ""
}

variable "common_tags" {
  description = "Tags applied to every generated azurerm_* resource (finops.resources_tagged) — the same set DEPLOY already applies imperatively to the resource group itself (attributionTags, worker/executors/deploy.ts)."
  type        = map(string)
  default     = {}
}
