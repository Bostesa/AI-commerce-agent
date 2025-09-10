#!/bin/bash

# Your registry name from the output above
REGISTRY_NAME="aicommerce1757482451"
RG="ai-commerce-rg"

echo "Using registry: $REGISTRY_NAME"

# Login to registry
az acr login --name $REGISTRY_NAME

# Build and push backend
echo "Building backend..."
az acr build --registry $REGISTRY_NAME --image backend:v1 ./backend

# Build and push frontend  
echo "Building frontend..."
az acr build --registry $REGISTRY_NAME --image frontend:v1 ./frontend

# Get credentials
REGISTRY_LOGIN_SERVER="$REGISTRY_NAME.azurecr.io"
REGISTRY_USERNAME=$(az acr credential show --name $REGISTRY_NAME --query username -o tsv)
REGISTRY_PASSWORD=$(az acr credential show --name $REGISTRY_NAME --query passwords[0].value -o tsv)

# Generate unique DNS labels
BACKEND_DNS="ai-commerce-backend-ns"
FRONTEND_DNS="ai-commerce-frontend-ns"

# Deploy backend
echo "Deploying backend..."
az container create \
  --resource-group $RG \
  --name backend \
  --image $REGISTRY_LOGIN_SERVER/backend:v1 \
  --registry-login-server $REGISTRY_LOGIN_SERVER \
  --registry-username $REGISTRY_USERNAME \
  --registry-password $REGISTRY_PASSWORD \
  --dns-name-label $BACKEND_DNS \
  --ports 8000 \
  --environment-variables ALLOWED_ORIGINS='*'

# Get backend URL
BACKEND_URL=$(az container show --resource-group $RG --name backend --query ipAddress.fqdn -o tsv)

# Deploy frontend
echo "Deploying frontend..."
az container create \
  --resource-group $RG \
  --name frontend \
  --image $REGISTRY_LOGIN_SERVER/frontend:v1 \
  --registry-login-server $REGISTRY_LOGIN_SERVER \
  --registry-username $REGISTRY_USERNAME \
  --registry-password $REGISTRY_PASSWORD \
  --dns-name-label $FRONTEND_DNS \
  --ports 3000 \
  --environment-variables NEXT_PUBLIC_BACKEND_URL="http://$BACKEND_URL:8000"

# Get URLs
FRONTEND_URL=$(az container show --resource-group $RG --name frontend --query ipAddress.fqdn -o tsv)

echo "====================================="
echo "Deployment complete!"
echo "Frontend: http://$FRONTEND_URL:3000"
echo "Backend: http://$BACKEND_URL:8000"
echo "====================================="