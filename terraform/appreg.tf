# create an Azure App Registration to connect to Graph API Email
resource "azuread_application" "graph" {
  display_name = "graph${local.func_name}app"
  owners       = [data.azurerm_client_config.current.object_id]
  sign_in_audience = "AzureADMyOrg" 

  required_resource_access {
    resource_app_id = "00000003-0000-0000-c000-000000000000" # Microsoft Graph

    resource_access {
      id   = "e1fe6dd8-ba31-4d61-89e7-88639da4683d" # User.Read
      type = "Scope"
    }
    resource_access {
        id   = "e2a3a72e-5f79-4c64-b1b1-878b674786c9" # Mail.ReadWrite
        type = "Role"
    }
  }

  web {
    implicit_grant {
      access_token_issuance_enabled = false
      id_token_issuance_enabled = true
    }
  }

  lifecycle {
    ignore_changes = [ web[0].redirect_uris ]
  }
}

resource "azuread_application_password" "graph" {
  application_id = azuread_application.graph.id
}