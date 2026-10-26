resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-${local.name}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 90
  tags                = local.tags
}

resource "azurerm_container_registry" "main" {
  name                = replace("acr${local.name}", "-", "")
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Standard"
  admin_enabled       = false
  tags                = local.tags
}

resource "azurerm_user_assigned_identity" "apps" {
  name                = "id-${local.name}-apps"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_role_assignment" "pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.apps.principal_id
}

resource "azurerm_container_app_environment" "main" {
  name                           = "cae-${local.name}"
  location                       = azurerm_resource_group.main.location
  resource_group_name            = azurerm_resource_group.main.name
  log_analytics_workspace_id     = azurerm_log_analytics_workspace.main.id
  infrastructure_subnet_id       = azurerm_subnet.apps.id
  internal_load_balancer_enabled = false
  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }
  tags = local.tags
}

locals {
  # Whether a key was given is not secret; the key itself stays sensitive.
  use_anthropic = nonsensitive(var.anthropic_api_key != "")

  db_host = azurerm_postgresql_flexible_server.main.fqdn
  # The app connects as copilot_app (created by the migration), never as the admin: row-level
  # security applies to it.
  secrets = {
    "database-url"       = "postgresql://copilot_app:${random_password.db_app.result}@${local.db_host}:5432/copilot?sslmode=require"
    "admin-database-url" = "postgresql://copilot_admin:${random_password.db_admin.result}@${local.db_host}:5432/copilot?sslmode=require"
    "app-db-password"    = random_password.db_app.result
    "token-secret"       = random_password.token_secret.result
    "metrics-token"      = random_password.metrics_token.result
  }
  env_from_secrets = {
    COPILOT_DATABASE_URL       = "database-url"
    COPILOT_ADMIN_DATABASE_URL = "admin-database-url"
    COPILOT_APP_DB_PASSWORD    = "app-db-password"
    COPILOT_TOKEN_SECRET       = "token-secret"
    COPILOT_METRICS_TOKEN      = "metrics-token"
  }
}

resource "azurerm_container_app" "api" {
  name                         = "ca-${local.name}-api"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.apps.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.apps.id
  }

  dynamic "secret" {
    for_each = local.secrets
    content {
      name  = secret.key
      value = secret.value
    }
  }

  dynamic "secret" {
    # A sensitive value cannot drive for_each, so only whether a key was given decides.
    for_each = local.use_anthropic ? toset(["anthropic-api-key"]) : toset([])
    content {
      name  = secret.value
      value = var.anthropic_api_key
    }
  }

  ingress {
    external_enabled = false # only the web app reaches the API
    target_port      = 8000
    transport        = "http"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 2
    max_replicas = 10

    http_scale_rule {
      name                = "concurrent-requests"
      concurrent_requests = "40"
    }

    container {
      name   = "api"
      image  = "${azurerm_container_registry.main.login_server}/copilot-api:${var.image_tag}"
      cpu    = 1
      memory = "2Gi"

      dynamic "env" {
        for_each = local.env_from_secrets
        content {
          name        = env.key
          secret_name = env.value
        }
      }

      dynamic "env" {
        for_each = local.use_anthropic ? toset(["anthropic-api-key"]) : toset([])
        content {
          name        = "ANTHROPIC_API_KEY"
          secret_name = env.value
        }
      }

      env {
        name  = "COPILOT_DEMO_MODE"
        value = "false"
      }

      liveness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/api/health"
      }

      readiness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/api/health"
      }
    }
  }

  tags       = local.tags
  depends_on = [azurerm_role_assignment.pull]
}

resource "azurerm_container_app" "web" {
  name                         = "ca-${local.name}-web"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.apps.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.apps.id
  }

  ingress {
    external_enabled = true
    target_port      = 8080
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 2
    max_replicas = 5
    container {
      name   = "web"
      image  = "${azurerm_container_registry.main.login_server}/copilot-web:${var.image_tag}"
      cpu    = 0.25
      memory = "0.5Gi"
      env {
        name  = "API_UPSTREAM"
        value = "https://${azurerm_container_app.api.ingress[0].fqdn}"
      }
    }
  }

  tags       = local.tags
  depends_on = [azurerm_role_assignment.pull]
}

# Migrations run as a job before each release (az containerapp job start), under an advisory lock.
resource "azurerm_container_app_job" "migrate" {
  name                         = "caj-${local.name}-migrate"
  location                     = azurerm_resource_group.main.location
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  workload_profile_name        = "Consumption"
  replica_timeout_in_seconds   = 600
  replica_retry_limit          = 2

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.apps.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.apps.id
  }

  dynamic "secret" {
    for_each = local.secrets
    content {
      name  = secret.key
      value = secret.value
    }
  }

  template {
    container {
      name    = "migrate"
      image   = "${azurerm_container_registry.main.login_server}/copilot-api:${var.image_tag}"
      command = ["copilot", "migrate"]
      cpu     = 0.5
      memory  = "1Gi"
      dynamic "env" {
        for_each = local.env_from_secrets
        content {
          name        = env.key
          secret_name = env.value
        }
      }
    }
  }

  tags       = local.tags
  depends_on = [azurerm_role_assignment.pull]
}
