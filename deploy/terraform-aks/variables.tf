variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus"
}

variable "cluster_name" {
  description = "AKS cluster name"
  type        = string
  default     = "pixeltable-app"
}

variable "resource_group_name" {
  description = "Azure resource group name"
  type        = string
  default     = "pixeltable-app-rg"
}

variable "vm_size" {
  description = "Azure VM size for AKS nodes"
  type        = string
  default     = "Standard_D4s_v3"
}

variable "node_count" {
  description = "Number of AKS nodes"
  type        = number
  default     = 2
}

variable "anthropic_api_key" {
  description = "Anthropic API key"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  sensitive   = true
}
