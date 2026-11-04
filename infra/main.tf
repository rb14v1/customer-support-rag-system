# Serves components: customer-support-api-app, frontend
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
  # Backend config supplied at init time via -backend-config flags (storage account/container/key
  # are resolved per app+environment by DEPLOY, not hardcoded here) — see lib/terraform-apply.ts.
  backend "azurerm" {}
}

provider "azurerm" {
  features {}
}


resource "azurerm_mssql_server" "sql" {
  tags = var.common_tags
  name                         = "sql-customer-supp-test-10"
  resource_group_name          = "customer-supp-test-10"
  location                     = "uksouth"
  version                      = "12.0"
  administrator_login          = "sqladmin"
  administrator_login_password = random_password.sql_admin.result
  public_network_access_enabled = false
}

resource "random_password" "sql_admin" {
  length  = 24
  special = true
}

resource "azurerm_mssql_database" "sql" {
  tags = var.common_tags
  name      = "db-customer-supp-test-10"
  server_id = azurerm_mssql_server.sql.id
  sku_name  = "Basic"
}

data "azurerm_private_dns_zone" "sql_dns_zone" {
  name                = "privatelink.database.windows.net"
  resource_group_name = var.hub_resource_group
}

resource "azurerm_private_dns_zone_virtual_network_link" "sql_dns_zone_link" {
  tags = var.common_tags
  name                  = "link-customer-supp-test-10"
  resource_group_name   = var.hub_resource_group
  private_dns_zone_name = data.azurerm_private_dns_zone.sql_dns_zone.name
  virtual_network_id    = var.vnet_id
}

resource "azurerm_private_endpoint" "sql_pe" {
  tags = var.common_tags
  name                = "pe-sql-customer-supp-test-10"
  resource_group_name = "customer-supp-test-10"
  location            = "uksouth"
  subnet_id           = var.subnet_id

  private_service_connection {
    name                           = "sql-privateserviceconnection"
    private_connection_resource_id = azurerm_mssql_server.sql.id
    subresource_names              = ["sqlServer"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "sql-dns-zone-group"
    private_dns_zone_ids = [data.azurerm_private_dns_zone.sql_dns_zone.id]
  }
}