variable "aws_region" {
  description = "AWS region to deploy resources in"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment name"
  type        = string
  default     = "production"
}

variable "project_name" {
  description = "Project name prefix for resources"
  type        = string
  default     = "entr-ai-plat"
}

variable "db_username" {
  description = "Username for the RDS PostgreSQL database"
  type        = string
  default     = "postgres"
}

variable "db_password" {
  description = "Password for the RDS PostgreSQL database"
  type        = string
  sensitive   = true
  default     = "SuperSecurePassword123!"
}

variable "openai_api_key" {
  description = "OpenAI API Key for embeddings and RAG evaluation"
  type        = string
  sensitive   = true
  default     = "sk-placeholder"
}

variable "cohere_api_key" {
  description = "Cohere API Key for reranking (optional)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "jwt_secret_key" {
  description = "JWT authentication signing key"
  type        = string
  sensitive   = true
  default     = "super-secret-jwt-signing-key-for-production"
}
