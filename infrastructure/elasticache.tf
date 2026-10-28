resource "aws_elasticache_subnet_group" "redis" {
  name       = "${var.project_name}-redis-subnet-group"
  subnet_ids = aws_subnet.private_data[*].id
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id        = "${var.project_name}-redis"
  description                 = "Redis cluster for celery backend and rate limiting"
  node_type                   = "cache.t4g.micro"
  port                        = 6379
  parameter_group_name        = "default.redis7"
  subnet_group_name           = aws_elasticache_subnet_group.redis.name
  security_group_ids          = [aws_security_group.redis.id]
  num_cache_clusters          = 1
  multi_az_enabled            = false
  automatic_failover_enabled  = false

  tags = {
    Name = "${var.project_name}-redis"
  }
}
