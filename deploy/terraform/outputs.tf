output "web_url" {
  value = "https://${azurerm_container_app.web.ingress[0].fqdn}"
}

output "registry" {
  value = azurerm_container_registry.main.login_server
}

output "postgres_fqdn" {
  value = azurerm_postgresql_flexible_server.main.fqdn
}
