output "alb_dns_name" {
  description = "Public DNS of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "ecr_repository_url" {
  description = "ECR Repository URL to push FastAPI Docker image"
  value       = aws_ecr_repository.api.repository_url
}

output "rds_postgres_endpoint" {
  description = "Connection endpoint for RDS PostgreSQL database"
  value       = aws_db_instance.postgres.endpoint
}

output "elasticache_redis_endpoint" {
  description = "Primary endpoint address for ElastiCache Redis replication group"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}
