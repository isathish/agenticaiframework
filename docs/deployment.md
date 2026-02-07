---
title: Deployment
description: Deploy AgenticAI Framework applications with Docker, Kubernetes, and cloud platforms
tags:
  - deployment
  - production
  - operations
  - guide
---

# Deployment

<div align="center">

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/isathish/agenticaiframework)
[![Modules](https://img.shields.io/badge/Modules-400%2B-purple.svg)](https://github.com/isathish/agenticaiframework)
[![Enterprise](https://img.shields.io/badge/Enterprise-237%20Modules-green.svg)](https://github.com/isathish/agenticaiframework)
[![Docker](https://img.shields.io/badge/Docker-Supported-2496ED?logo=docker&logoColor=white)](https://hub.docker.com)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-Ready-326CE5?logo=kubernetes&logoColor=white)](https://kubernetes.io)

</div>

!!! success "Enterprise Deployment"
    Part of **237 enterprise modules** with **20 infrastructure features** for production deployments. See [Enterprise Documentation](enterprise.md).

---

## Overview

This comprehensive guide covers deploying AgenticAI Framework applications across various environments, from local development to production-scale cloud deployments.

## Deployment Options

```mermaid
graph TB
    subgraph "Development"
        LOCAL[Local Development<br/>Python + venv]
        DOCKER_LOCAL[Docker Compose<br/>Multi-container]
    end

    subgraph "Staging/Testing"
        VM[Virtual Machines<br/>EC2, Azure VM]
        CONTAINER[Container Registry<br/>Docker Hub, ACR, ECR]
    end

    subgraph "Production - Compute"
        K8S[Kubernetes<br/>EKS, AKS, GKE]
        SERVERLESS[Serverless<br/>Lambda, Functions]
        APP_PLATFORM[App Platform<br/>App Engine, Elastic Beanstalk]
    end

    subgraph "Production - Managed"
        PAAS[Platform as Service<br/>Heroku, Render]
        FAAS[Functions as Service<br/>AWS Lambda, Azure Functions]
    end

    LOCAL --> DOCKER_LOCAL
    DOCKER_LOCAL --> CONTAINER
    CONTAINER --> K8S
    CONTAINER --> APP_PLATFORM
    VM --> K8S

    style LOCAL fill:#4caf50
    style K8S fill:#2196f3
    style SERVERLESS fill:#ff9800
```

## Docker Deployment

### 1. Dockerfile

```dockerfile
# Multi-stage build for optimal image size
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY . .

# Update PATH
ENV PATH=/root/.local/bin:$PATH

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Expose port
EXPOSE 8000

# Run application
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2. Docker Compose

```yaml
version: '3.8'

services:
  # Main application
  agentic-ai:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - REDIS_URL=redis://redis:6379/0
      - POSTGRES_URL=postgresql://postgres:password@postgres:5432/agenticai
    depends_on:
      - redis
      - postgres
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - agentic-network

  # Redis cache
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes
    restart: unless-stopped
    networks:
      - agentic-network

  # PostgreSQL database
  postgres:
    image: postgres:15-alpine
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=agenticai
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres-data:/var/lib/postgresql/data
    restart: unless-stopped
    networks:
      - agentic-network

  # Monitoring - Prometheus
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    restart: unless-stopped
    networks:
      - agentic-network

  # Monitoring - Grafana
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana
    restart: unless-stopped
    networks:
      - agentic-network

volumes:
  redis-data:
  postgres-data:
  prometheus-data:
  grafana-data:

networks:
  agentic-network:
    driver: bridge
```

### 3. Build and Run

```bash
# Build Docker image
docker build -t agenticai-framework:latest .

# Run container
docker run -d \
  --name agenticai-app \
  -p 8000:8000 \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  agenticai-framework:latest

# Run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f agentic-ai

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## Kubernetes Deployment

### 1. Kubernetes Manifests

#### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agenticai-deployment
  labels:
    app: agenticai
spec:
  replicas: 3
  selector:
    matchLabels:
      app: agenticai
  template:
    metadata:
      labels:
        app: agenticai
    spec:
      containers:
      - name: agenticai
        image: your-registry/agenticai-framework:latest
        ports:
        - containerPort: 8000
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: agenticai-secrets
              key: openai-api-key
        - name: REDIS_URL
          value: "redis://redis-service:6379/0"
        - name: POSTGRES_URL
          valueFrom:
            secretKeyRef:
              name: agenticai-secrets
              key: postgres-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

#### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: agenticai-service
spec:
  selector:
    app: agenticai
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

#### ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: agenticai-config
data:
  LOG_LEVEL: "INFO"
  MAX_AGENTS: "50"
  TIMEOUT_SECONDS: "30"
  ENABLE_MONITORING: "true"
```

#### Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: agenticai-secrets
type: Opaque
stringData:
  openai-api-key: "sk-your-api-key-here"
  postgres-url: "postgresql://user:pass@postgres:5432/db"
```

### 2. Helm Chart

```yaml
# values.yaml
replicaCount: 3

image:
  repository: your-registry/agenticai-framework
  tag: latest
  pullPolicy: IfNotPresent

service:
  type: LoadBalancer
  port: 80

resources:
  limits:
    cpu: 2000m
    memory: 2Gi
  requests:
    cpu: 500m
    memory: 512Mi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

secrets:
  openaiApiKey: ""
  postgresUrl: ""

config:
  logLevel: "INFO"
  maxAgents: 50
  timeoutSeconds: 30
```

### 3. Deploy to Kubernetes

```bash
# Apply manifests
kubectl apply -f kubernetes/

# Or use Helm
helm install agenticai ./helm-chart -f values.yaml

# Check deployment
kubectl get deployments
kubectl get pods
kubectl get services

# View logs
kubectl logs -f deployment/agenticai-deployment

# Scale deployment
kubectl scale deployment/agenticai-deployment --replicas=5

# Update deployment
kubectl set image deployment/agenticai-deployment \
  agenticai=your-registry/agenticai-framework:v1.2.13

# Delete deployment
kubectl delete -f kubernetes/
# or
helm uninstall agenticai
```

## Cloud Platform Deployments

### 1. AWS Deployment

#### AWS Elastic Beanstalk

```bash
# Install EB CLI
pip install awsebcli

# Initialize EB application
eb init -p python-3.11 agenticai-app

# Create environment
eb create agenticai-env

# Deploy application
eb deploy

# Open in browser
eb open

# View logs
eb logs

# SSH into instance
eb ssh

# Terminate environment
eb terminate agenticai-env
```

#### AWS ECS (Fargate)

```json
{
  "family": "agenticai-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [{
      "name": "agenticai",
      "image": "your-registry/agenticai-framework:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [{
          "name": "LOG_LEVEL",
          "value": "INFO"
        }
      ],
      "secrets": [{
          "name": "OPENAI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:openai-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/agenticai",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### 2. Azure Deployment

#### Azure Container Instances

```bash
# Create resource group
az group create --name agenticai-rg --location eastus

# Create container instance
az container create \
  --resource-group agenticai-rg \
  --name agenticai-container \
  --image your-registry/agenticai-framework:latest \
  --cpu 2 \
  --memory 4 \
  --ports 8000 \
  --dns-name-label agenticai-app \
  --environment-variables \
    LOG_LEVEL=INFO \
    MAX_AGENTS=50 \
  --secure-environment-variables \
    OPENAI_API_KEY=$OPENAI_API_KEY

# Get container status
az container show \
  --resource-group agenticai-rg \
  --name agenticai-container \
  --query "{FQDN:ipAddress.fqdn,ProvisioningState:provisioningState}" \
  --out table

# View logs
az container logs \
  --resource-group agenticai-rg \
  --name agenticai-container

# Delete container
az container delete \
  --resource-group agenticai-rg \
  --name agenticai-container \
  --yes
```

#### Azure Kubernetes Service (AKS)

```bash
# Create AKS cluster
az aks create \
  --resource-group agenticai-rg \
  --name agenticai-aks \
  --node-count 3 \
  --enable-addons monitoring \
  --generate-ssh-keys

# Get credentials
az aks get-credentials \
  --resource-group agenticai-rg \
  --name agenticai-aks

# Deploy application
kubectl apply -f kubernetes/

# Get service external IP
kubectl get service agenticai-service

# Scale cluster
az aks scale \
  --resource-group agenticai-rg \
  --name agenticai-aks \
  --node-count 5
```

### 3. Google Cloud Platform

#### Google Cloud Run

```bash
# Build and push image
gcloud builds submit --tag gcr.io/PROJECT_ID/agenticai-framework

# Deploy to Cloud Run
gcloud run deploy agenticai-service \
  --image gcr.io/PROJECT_ID/agenticai-framework \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars LOG_LEVEL=INFO \
  --set-secrets OPENAI_API_KEY=openai-key:latest

# Update service
gcloud run services update agenticai-service \
  --region us-central1 \
  --memory 2Gi \
  --cpu 2 \
  --max-instances 10

# View logs
gcloud run services logs read agenticai-service --region us-central1

# Delete service
gcloud run services delete agenticai-service --region us-central1
```

#### Google Kubernetes Engine (GKE)

```bash
# Create GKE cluster
gcloud container clusters create agenticai-cluster \
  --num-nodes 3 \
  --machine-type n1-standard-2 \
  --region us-central1

# Get credentials
gcloud container clusters get-credentials agenticai-cluster \
  --region us-central1

# Deploy application
kubectl apply -f kubernetes/

# Expose service
kubectl expose deployment agenticai-deployment \
  --type LoadBalancer \
  --port 80 \
  --target-port 8000
```

## Security Configuration

### 1. Environment Variables

```bash
# .env file (never commit to git)
OPENAI_API_KEY=sk-your-api-key
ANTHROPIC_API_KEY=sk-ant-your-key
POSTGRES_URL=postgresql://user:pass@localhost:5432/db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-here
LOG_LEVEL=INFO
ENABLE_MONITORING=true
```

### 2. Secrets Management

```python
# Use cloud provider secret managers
import boto3
from azure.keyvault.secrets import SecretClient
from google.cloud import secretmanager

# AWS Secrets Manager
def get_aws_secret(secret_name: str):
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return response['SecretString']

# Azure Key Vault
def get_azure_secret(vault_url: str, secret_name: str):
    client = SecretClient(vault_url=vault_url, credential=credential)
    secret = client.get_secret(secret_name)
    return secret.value

# Google Secret Manager
def get_gcp_secret(project_id: str, secret_id: str):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode('UTF-8')
```

## Monitoring & Health Checks

### 1. Health Check Endpoints

```python
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/health")
async def health_check():
    """Basic health check"""
    return {"status": "healthy"}

@app.get("/ready")
async def readiness_check():
    """Readiness check with dependencies"""

    checks = {
        "database": check_database(),
        "redis": check_redis(),
        "llm_service": check_llm_service()
    }

    all_healthy = all(checks.values())
    status_code = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_healthy else "not_ready",
            "checks": checks
        }
    )

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return prometheus_client.generate_latest()
```

### 2. Logging Configuration

```python
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)

logger = logging.getLogger(__name__)

# Structured logging
import json

def log_structured(level: str, message: str, **kwargs):
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "message": message,
        **kwargs
    }
    logger.info(json.dumps(log_entry))

log_structured("INFO", "Agent started", agent_id="agent_001", task="analysis")
```

## CI/CD Pipeline

### GitHub Actions

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]
    tags: ['v*']

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov

    - name: Run tests
      run: pytest --cov=agenticaiframework tests/

    - name: Build Docker image
      run: |
        docker build -t ${{ secrets.REGISTRY }}/agenticai:${{ github.sha }} .
        docker tag ${{ secrets.REGISTRY }}/agenticai:${{ github.sha }} \
                   ${{ secrets.REGISTRY }}/agenticai:latest

    - name: Push to registry
      run: |
        echo ${{ secrets.REGISTRY_PASSWORD }} | docker login -u ${{ secrets.REGISTRY_USERNAME }} --password-stdin
        docker push ${{ secrets.REGISTRY }}/agenticai:${{ github.sha }}
        docker push ${{ secrets.REGISTRY }}/agenticai:latest

    - name: Deploy to Kubernetes
      uses: azure/k8s-deploy@v4
      with:
        manifests: |
          kubernetes/deployment.yaml
          kubernetes/service.yaml
        images: |
          ${{ secrets.REGISTRY }}/agenticai:${{ github.sha }}
        kubectl-version: 'latest'
```

## Related Documentation

- [Performance Optimization](performance.md) - Speed and efficiency
- [Architecture Overview](architecture.md) - System design
- [Monitoring](monitoring.md) - Observability
- [Security](security.md) - Security best practices
- [Best Practices](best-practices.md) - Development guidelines

<div align="center">

**[Back to Top](#deployment-guide)**

</div>
