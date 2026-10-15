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


resource "azurerm_search_service" "search" {
  name                = "search-cust-rag-afgh"
  resource_group_name = "cust-rag-afgh"
  location            = "uksouth"
  sku                 = "basic"
  public_network_access_enabled = false
}

resource "azurerm_private_dns_zone" "search_dns_zone" {
  name                = "privatelink.search.windows.net"
  resource_group_name = "cust-rag-afgh"
}

resource "azurerm_private_dns_zone_virtual_network_link" "search_dns_zone_link" {
  name                  = "link-cust-rag-afgh"
  resource_group_name   = "cust-rag-afgh"
  private_dns_zone_name = azurerm_private_dns_zone.search_dns_zone.name
  virtual_network_id    = var.vnet_id
}

resource "azurerm_private_endpoint" "search_pe" {
  name                = "pe-search-cust-rag-afgh"
  resource_group_name = "cust-rag-afgh"
  location            = "uksouth"
  subnet_id           = var.subnet_id

  private_service_connection {
    name                           = "search-privateserviceconnection"
    private_connection_resource_id = azurerm_search_service.search.id
    subresource_names              = ["searchService"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "search-dns-zone-group"
    private_dns_zone_ids = [azurerm_private_dns_zone.search_dns_zone.id]
  }
}

resource "azurerm_storage_account" "blob" {
  name                     = "stcustragafgh"
  resource_group_name      = "cust-rag-afgh"
  location                 = "uksouth"
  account_tier             = "Standard"
  account_replication_type = "LRS"
  public_network_access_enabled = false
}

resource "azurerm_private_dns_zone" "blob_dns_zone" {
  name                = "privatelink.blob.core.windows.net"
  resource_group_name = "cust-rag-afgh"
}

resource "azurerm_private_dns_zone_virtual_network_link" "blob_dns_zone_link" {
  name                  = "link-cust-rag-afgh"
  resource_group_name   = "cust-rag-afgh"
  private_dns_zone_name = azurerm_private_dns_zone.blob_dns_zone.name
  virtual_network_id    = var.vnet_id
}

resource "azurerm_private_endpoint" "blob_pe" {
  name                = "pe-blob-cust-rag-afgh"
  resource_group_name = "cust-rag-afgh"
  location            = "uksouth"
  subnet_id           = var.subnet_id

  private_service_connection {
    name                           = "blob-privateserviceconnection"
    private_connection_resource_id = azurerm_storage_account.blob.id
    subresource_names              = ["blob"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "blob-dns-zone-group"
    private_dns_zone_ids = [azurerm_private_dns_zone.blob_dns_zone.id]
  }
}

resource "azurerm_log_analytics_workspace" "law" {
  name                = "law-cust-rag-afgh"
  resource_group_name = "cust-rag-afgh"
  location            = "uksouth"
  sku                 = "PerGB2018"
  retention_in_days   = 30
}