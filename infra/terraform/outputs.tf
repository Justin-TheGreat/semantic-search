output "cluster_name" {
  value = kind_cluster.ragship.name
}

output "kubeconfig_path" {
  value = kind_cluster.ragship.kubeconfig_path
}

output "api_url" {
  description = "The RAGShip API as exposed on the host via the kind port mapping"
  value       = "http://localhost:8080"
}
