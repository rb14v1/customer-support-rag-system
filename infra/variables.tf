variable "vnet_id" {
  description = "ID of the one shared, VNet-integrated Container Apps Environment's virtual network."
  type        = string
}

variable "subnet_id" {
  description = "ID of the subnet private endpoints attach to, inside the shared VNet."
  type        = string
}
