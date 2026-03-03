variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
  default     = "pixeltable-starter"
}

variable "node_instance_type" {
  description = "EC2 instance type for EKS worker nodes"
  type        = string
  default     = "m6i.xlarge"
}

variable "node_count" {
  description = "Number of EKS worker nodes"
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

variable "ecr_repository_name" {
  description = "ECR repository name for the app image"
  type        = string
  default     = "pixeltable-starter"
}
