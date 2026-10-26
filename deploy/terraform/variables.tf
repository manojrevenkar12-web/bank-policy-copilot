variable "location" {
  type    = string
  default = "germanywestcentral" # Frankfurt: bank data stays in Germany
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "image_tag" {
  type        = string
  description = "Tag of copilot-api and copilot-web in the registry (set by the release pipeline)."
  default     = "0.1.0"
}

variable "postgres_sku" {
  type    = string
  default = "GP_Standard_D2ds_v5"
}

variable "anthropic_api_key" {
  type        = string
  description = "Optional. Empty keeps every answer in process (extractive)."
  default     = ""
  sensitive   = true
}
