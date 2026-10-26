resource "random_password" "db_admin" {
  length  = 32
  special = false
}

resource "random_password" "db_app" {
  length  = 32
  special = false
}

resource "random_password" "token_secret" {
  length  = 48
  special = false
}

resource "random_password" "metrics_token" {
  length  = 32
  special = false
}

resource "azurerm_postgresql_flexible_server" "main" {
  name                          = "psql-${local.name}"
  resource_group_name           = azurerm_resource_group.main.name
  location                      = azurerm_resource_group.main.location
  version                       = "16"
  sku_name                      = var.postgres_sku
  storage_mb                    = 65536
  backup_retention_days         = 35
  geo_redundant_backup_enabled  = false
  delegated_subnet_id           = azurerm_subnet.db.id
  private_dns_zone_id           = azurerm_private_dns_zone.db.id
  public_network_access_enabled = false
  administrator_login           = "copilot_admin"
  administrator_password        = random_password.db_admin.result
  zone                          = "1"

  high_availability {
    mode                      = "ZoneRedundant"
    standby_availability_zone = "2"
  }

  tags       = local.tags
  depends_on = [azurerm_private_dns_zone_virtual_network_link.db]
}

# pgvector must be allow-listed before CREATE EXTENSION vector (migration 001).
resource "azurerm_postgresql_flexible_server_configuration" "extensions" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "VECTOR"
}

resource "azurerm_postgresql_flexible_server_configuration" "slow_queries" {
  name      = "log_min_duration_statement"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "500"
}

resource "azurerm_postgresql_flexible_server_database" "copilot" {
  name      = "copilot"
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}
