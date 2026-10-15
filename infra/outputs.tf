
output "ai_search_admin_key" {
  value     = azurerm_search_service.search.primary_key
  sensitive = true
}
output "ai_search_service_id" {
  value = azurerm_search_service.search.id
}
output "ai_search_endpoint" {
  value = "https://${azurerm_search_service.search.name}.search.windows.net"
}

output "blob_storage_connection" {
  value     = azurerm_storage_account.blob.primary_connection_string
  sensitive = true
}
output "blob_storage_account_id" {
  value = azurerm_storage_account.blob.id
}

output "log_analytics_workspace_id" {
  value = azurerm_log_analytics_workspace.law.workspace_id
}