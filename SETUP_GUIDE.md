# Assignment 7 - Kubernetes Autoscaling and Stress Testing

## Overview
This assignment extends the IRIS classification pipeline with:
- OpenTelemetry logging and tracing
- Kubernetes HorizontalPodAutoscaler (HPA)
- Automated stress testing with wrk
- Performance bottleneck analysis

## Prerequisites
- GCP Project with billing enabled
- GitHub repository with secrets configured
- Docker installed locally (optional for local testing)

## Step-by-Step Setup Guide

### 1. Enable Required GCP Services

```bash
# Enable necessary APIs
gcloud services enable container.googleapis.com \
    logging.googleapis.com \
    monitoring.googleapis.com \
    cloudtrace.googleapis.com
```

### 2. Create GKE Cluster

```bash
# Set your project ID
export PROJECT_ID=$(gcloud config get-value project)

# Create cluster with workload identity and monitoring enabled
gcloud container clusters create iris-ml-cluster \
  --zone=us-central1-a \
  --num-nodes=3 \
  --workload-pool=$PROJECT_ID.svc.id.goog \
  --logging=SYSTEM,WORKLOAD \
  --monitoring=SYSTEM \
  --enable-autoscaling \
  --min-nodes=1 \
  --max-nodes=5
```

### 3. Create Service Account for Telemetry

```bash
# Create GCP service account
gcloud iam service-accounts create telemetry-access \
    --display-name "Access for GKE ML service"

# Grant logging permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:telemetry-access@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/logging.logWriter"

# Grant tracing permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:telemetry-access@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/cloudtrace.agent"

# Grant monitoring permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:telemetry-access@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/monitoring.metricWriter"
```

### 4. Configure Workload Identity (Do this EVERY time you create a new cluster)

```bash
# Get cluster credentials
gcloud container clusters get-credentials iris-ml-cluster \
  --zone=us-central1-a

# If you get auth plugin error on Compute Engine/Workbench:
# sudo apt-get install google-cloud-cli-gke-gcloud-auth-plugin
# gcloud config set container/use_application_default_credentials true

# Create Kubernetes service account
kubectl create serviceaccount telemetry-access --namespace default

# Annotate K8s service account with GCP service account
kubectl annotate serviceaccount telemetry-access \
  --namespace default \
  iam.gke.io/gcp-service-account=telemetry-access@$PROJECT_ID.iam.gserviceaccount.com

# Bind GCP service account to K8s service account
gcloud iam service-accounts add-iam-policy-binding telemetry-access@$PROJECT_ID.iam.gserviceaccount.com \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:$PROJECT_ID.svc.id.goog[default/telemetry-access]"
```

### 5. Verify Workload Identity Setup

```bash
# Check if service account exists
kubectl get serviceaccount telemetry-access -n default

# Check annotation
kubectl describe serviceaccount telemetry-access -n default

# Check IAM policy
gcloud iam service-accounts get-iam-policy telemetry-access@$PROJECT_ID.iam.gserviceaccount.com
```

### 6. Create Artifact Registry Repository

```bash
# Create repository (if not exists)
gcloud artifacts repositories create my-repo \
    --repository-format=docker \
    --location=us-central1 \
    --description="Docker repository for ML services"

# Configure Docker authentication
gcloud auth configure-docker us-central1-docker.pkg.dev
```

### 7. Build and Push Docker Image (Local Testing - Optional)

```bash
# Build the image
docker build -t iris-api:latest .

# Tag the image
docker tag iris-api:latest us-central1-docker.pkg.dev/$PROJECT_ID/my-repo/iris-api:latest

# Push to Artifact Registry
docker push us-central1-docker.pkg.dev/$PROJECT_ID/my-repo/iris-api:latest
```

### 8. Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add the following secrets:
- `GCP_SA_KEY`: Service account JSON key with permissions for GKE and Artifact Registry
- `GCP_PROJECT_ID`: Your GCP project ID (e.g., `bold-result-474211-u3`)
- `GCP_REGION`: Region for your resources (e.g., `us-central1`)
- `GKE_CLUSTER_NAME`: Name of your GKE cluster (e.g., `iris-ml-cluster`)

To create the service account key:
```bash
gcloud iam service-accounts create github-actions \
    --display-name "GitHub Actions"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/container.developer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud iam service-accounts keys create github-sa-key.json \
  --iam-account=github-actions@$PROJECT_ID.iam.gserviceaccount.com

# Copy the contents of github-sa-key.json to GCP_SA_KEY secret
cat github-sa-key.json
```

### 9. Manual Deployment (Alternative to CI/CD)

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/hpa.yaml

# Check deployment status
kubectl rollout status deployment/iris-api-deployment

# Get service external IP
kubectl get service iris-api-service

# Wait for EXTERNAL-IP to be assigned (may take 1-2 minutes)
```

### 10. Configure VPC Firewall Rules

```bash
# Allow traffic on port 80
gcloud compute firewall-rules create allow-iris-api \
    --allow tcp:80 \
    --source-ranges 0.0.0.0/0 \
    --description "Allow traffic to IRIS API"
```

### 11. Test the Deployment

```bash
# Get the external IP
EXTERNAL_IP=$(kubectl get service iris-api-service -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

echo "Service URL: http://$EXTERNAL_IP:80"

# Test the prediction endpoint
curl -X POST http://$EXTERNAL_IP:80/predict \
  -H "Content-Type: application/json" \
  -d '{"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2}'
```

### 12. Run Stress Tests

```bash
# Install wrk (on Ubuntu/Debian)
sudo apt-get install wrk

# Test with 1000 concurrent connections
wrk -t4 -c1000 -d30s --latency -s post.lua http://$EXTERNAL_IP:80/predict

# Check HPA status
kubectl get hpa iris-api-hpa

# Check pod scaling
kubectl get pods -l app=iris-api

# Test with 2000 concurrent connections (observe bottleneck)
wrk -t4 -c2000 -d30s --latency -s post.lua http://$EXTERNAL_IP:80/predict

# Monitor in real-time
watch -n 2 'kubectl get hpa iris-api-hpa && echo "" && kubectl get pods -l app=iris-api'
```

### 13. Observe Autoscaling Behavior

```bash
# Watch HPA in real-time
kubectl get hpa iris-api-hpa --watch

# Watch pods scaling
kubectl get pods -l app=iris-api --watch

# Check pod resource usage
kubectl top pods -l app=iris-api

# Check detailed pod status
kubectl describe pods -l app=iris-api
```

### 14. View Logs and Telemetry in GCP Console

1. **Cloud Logging**: Go to Logging → Logs Explorer
   - Filter: `resource.type="k8s_container" resource.labels.container_name="iris-api"`

2. **Cloud Trace**: Go to Trace → Trace List
   - View latency distribution and request traces

3. **Cloud Monitoring**: Go to Monitoring → Dashboards
   - View CPU usage, memory, request rates

### 15. Test Bottleneck with 1 Pod Maximum

```bash
# Edit HPA to restrict to 1 pod
kubectl patch hpa iris-api-hpa -p '{"spec":{"maxReplicas":1}}'

# Run stress test with 1000 connections
wrk -t4 -c1000 -d30s --latency -s post.lua http://$EXTERNAL_IP:80/predict

# Save results for comparison

# Run stress test with 2000 connections
wrk -t4 -c2000 -d30s --latency -s post.lua http://$EXTERNAL_IP:80/predict

# Observe degraded performance (higher latency, lower throughput)

# Restore HPA to 3 pods max
kubectl patch hpa iris-api-hpa -p '{"spec":{"maxReplicas":3}}'
```

### 16. Force Image Update (if needed)

```bash
# Rollout restart to pull latest image
kubectl rollout restart deployment/iris-api-deployment

# Check rollout status
kubectl rollout status deployment/iris-api-deployment

# Check pod age
kubectl get pods -l app=iris-api

# Check image being used
kubectl describe pod <pod-name> | grep Image
```

### 17. Cleanup Resources

```bash
# Delete Kubernetes resources
kubectl delete -f k8s/

# Delete GKE cluster
gcloud container clusters delete iris-ml-cluster --zone=us-central1-a

# Delete firewall rule
gcloud compute firewall-rules delete allow-iris-api

# Delete service accounts (optional)
gcloud iam service-accounts delete telemetry-access@$PROJECT_ID.iam.gserviceaccount.com
gcloud iam service-accounts delete github-actions@$PROJECT_ID.iam.gserviceaccount.com
```

## Key Observations

### With Autoscaling (1-3 pods):
- Initial latency: ~100ms
- Under 1000 requests: HPA scales to 2-3 pods
- Throughput: Increases as pods scale
- P99 latency: Remains reasonable (~200-300ms)

### With 1 Pod Maximum:
- Initial latency: ~100ms
- Under 1000 requests: Single pod gets overwhelmed
- CPU throttling occurs
- Throughput: Limited by single pod capacity
- P99 latency: Significantly higher (~500-1000ms+)
- With 2000 requests: Severe degradation, possible timeouts

### Bottleneck Analysis:
1. **CPU**: Reaches 100% utilization on single pod
2. **Connection Queue**: Requests wait longer in queue
3. **Response Time**: Increases exponentially under load
4. **Failure Rate**: May see 5xx errors under extreme load

## Troubleshooting

### Pods stuck in CrashLoopBackOff:
```bash
kubectl logs <pod-name>
kubectl describe pod <pod-name>
```

### HPA not scaling:
```bash
# Check metrics server
kubectl get apiservice v1beta1.metrics.k8s.io

# Check HPA events
kubectl describe hpa iris-api-hpa
```

### Service IP not assigned:
```bash
# Check service events
kubectl describe service iris-api-service

# Check LoadBalancer status
kubectl get service iris-api-service -o yaml
```

### Telemetry not appearing in GCP:
```bash
# Verify workload identity
kubectl describe serviceaccount telemetry-access

# Check pod logs
kubectl logs <pod-name>

# Test from pod
kubectl exec -it <pod-name> -- env | grep GOOGLE
```

## Assignment Deliverables

1. **Updated CI/CD Pipeline**: GitHub Actions workflow with stress testing
2. **HPA Configuration**: YAML manifest with 1 min, 3 max replicas
3. **Stress Test Results**:
   - wrk output for 1000 connections
   - wrk output for 2000 connections
   - Comparison with 1 pod vs 3 pods max
4. **Bottleneck Analysis**: Report showing:
   - Latency increase
   - Throughput degradation
   - CPU utilization
   - HPA scaling behavior
5. **Screenshots**:
   - GCP Cloud Logging
   - GCP Cloud Trace
   - HPA scaling in action
   - Pod resource usage

## References
- [Kubernetes HPA Documentation](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/instrumentation/python/)
- [wrk Benchmarking Tool](https://github.com/wg/wrk)
- [GKE Workload Identity](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)
