#!/bin/bash

# Set your registry name from step 4
REGISTRY_NAME="aicommerce12345"  # <-- Replace with your actual registry name
RG="ai-commerce-rg"

# Login to registry
az acr login --name $REGISTRY_NAME

# Build and push backend (from your local backend folder)
echo "Building backend..."
az acr build --registry $REGISTRY_NAME --image backend:v1 ./backend

# Build and push frontend (from your local frontend folder)
echo "Building frontend..."
az acr build --registry $REGISTRY_NAME --image frontend:v1 ./frontend

# Get registry credentials
REGISTRY_LOGIN_SERVER="$REGISTRY_NAME.azurecr.io"
REGISTRY_USERNAME=$(az acr credential show --name $REGISTRY_NAME --query username -o tsv)
REGISTRY_PASSWORD=$(az acr credential show --name $REGISTRY_NAME --query passwords[0].value -o tsv)

# Deploy backend
echo "Deploying backend..."
az container create \
  --resource-group $RG \
  --name backend \
  --image $REGISTRY_LOGIN_SERVER/backend:v1 \
  --registry-login-server $REGISTRY_LOGIN_SERVER \
  --registry-username $REGISTRY_USERNAME \
  --registry-password $REGISTRY_PASSWORD \
  --dns-name-label ai-commerce-backend-$RANDOM \
  --ports 8000 \
  --environment-variables ALLOWED_ORIGINS='*'

# Get backend URL
BACKEND_URL=$(az container show --resource-group $RG --name backend --query ipAddress.fqdn -o tsv)

# Deploy frontend with backend URL
echo "Deploying frontend..."
az container create \
  --resource-group $RG \
  --name frontend \
  --image $REGISTRY_LOGIN_SERVER/frontend:v1 \
  --registry-login-server $REGISTRY_LOGIN_SERVER \
  --registry-username $REGISTRY_USERNAME \
  --registry-password $REGISTRY_PASSWORD \
  --dns-name-label ai-commerce-frontend-$RANDOM \
  --ports 3000 \
  --environment-variables NEXT_PUBLIC_BACKEND_URL="http://$BACKEND_URL:8000"

# Get frontend URL
FRONTEND_URL=$(az container show --resource-group $RG --name frontend --query ipAddress.fqdn -o tsv)

echo "====================================="
echo "Deployment complete!"
echo "Frontend: http://$FRONTEND_URL:3000"
echo "Backend: http://$BACKEND_URL:8000"
echo "====================================="