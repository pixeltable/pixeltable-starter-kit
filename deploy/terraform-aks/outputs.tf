output "cluster_name" {
  description = "AKS cluster name"
  value       = azurerm_kubernetes_cluster.aks.name
}

output "acr_login_server" {
  description = "ACR login server for pushing images"
  value       = azurerm_container_registry.acr.login_server
}

output "load_balancer_ip" {
  description = "App load balancer IP"
  value       = kubernetes_service.app.status[0].load_balancer[0].ingress[0].ip
}

output "configure_kubectl" {
  description = "Command to configure kubectl"
  value       = "az aks get-credentials --resource-group ${azurerm_resource_group.rg.name} --name ${azurerm_kubernetes_cluster.aks.name}"
}
