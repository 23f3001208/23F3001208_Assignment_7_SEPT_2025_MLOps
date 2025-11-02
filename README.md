# Iris Classifier API - MLOps Assignment

This project implements a machine learning API for classifying Iris flower species using a trained model. It includes FastAPI endpoints for predictions, containerization with Docker, and deployment to Google Kubernetes Engine (GKE) via GitHub Actions CI/CD.

## Setup Instructions

### Prerequisites

- Python 3.10 or higher
- Docker
- kubectl (for Kubernetes deployment)
- Google Cloud SDK (for GKE deployment)
- A Google Cloud Project with GKE cluster and Artifact Registry set up

### Local Development Setup

1. Clone the repository:

   ```
   git clone https://github.com/23f3001208/23F3001208_Assignment_6_SEPT_2025_MLOps.git
   cd 23F3001208_Assignment_6_SEPT_2025_MLOps
   ```

2. Install Python dependencies:

   ```
   pip install -r requirements.txt
   ```

3. Run the API locally (using train_2.py as the main app):

   ```
   uvicorn train_2:app --host 0.0.0.0 --port 8200 --reload
   ```

4. Test the API:
   - Open http://localhost:8200/docs for FastAPI interactive docs
   - Send a POST request to `/predict/` with JSON body:
     ```json
     {
       "sepal_length": 5.1,
       "sepal_width": 3.5,
       "petal_length": 1.4,
       "petal_width": 0.2
     }
     ```

### Docker Setup

1. Build the Docker image:

   ```
   docker build -t iris-api:latest .
   ```

2. Run the container locally:
   ```
   docker run -p 8200:8200 iris-api:latest
   ```

### Kubernetes Deployment

1. Ensure you have access to your GKE cluster:

   ```
   gcloud container clusters get-credentials <cluster-name> --region <region> --project <project-id>
   ```

2. Apply the Kubernetes manifests:

   ```
   kubectl apply -f k8s/deployment.yaml
   kubectl apply -f k8s/service.yaml
   ```

3. Check deployment status:
   ```
   kubectl rollout status deployment/iris-api-deployment
   kubectl get services
   ```

### CI/CD Deployment

The project includes GitHub Actions workflow for automatic deployment to GKE on pushes to the main branch. Ensure the following secrets are set in your GitHub repository:

- GCP_SA_KEY: Google Cloud Service Account key JSON
- GCP_REGION: Google Cloud region
- GCP_PROJECT_ID: Google Cloud project ID
- GKE_CLUSTER_NAME: GKE cluster name

## File Explanations

### train_1.py

A FastAPI application that serves as an Iris classifier API. It loads a pre-trained model from `model.joblib` and provides endpoints for predictions. Uses NumPy for data handling. This version uses NumPy arrays for input processing.

**Utility**: Provides a REST API for Iris species classification using the first implementation approach with NumPy.

### train_2.py

Similar to train_1.py, this is another FastAPI application for Iris classification. It uses pandas DataFrames for input processing instead of NumPy arrays. This is the main application file referenced in the Dockerfile.

**Utility**: Alternative implementation of the Iris classifier API using pandas for data manipulation, offering flexibility in data handling approaches.

### Dockerfile

Defines the Docker image for containerizing the FastAPI application. It uses Python 3.10-slim as the base image, copies project files, installs dependencies, exposes port 8200, and runs the app with uvicorn.

**Utility**: Enables containerization of the API for consistent deployment across environments, including local development and cloud platforms.

### requirements.txt

Lists all Python dependencies required for the project, including FastAPI, uvicorn, pydantic, joblib, numpy, and scikit-learn.

**Utility**: Ensures reproducible installations of dependencies across different environments and simplifies setup for developers and deployment pipelines.

### model.joblib

A serialized machine learning model file (likely a scikit-learn model) trained on the Iris dataset for species classification.

**Utility**: Contains the pre-trained model used by the API for making predictions. This file is loaded at runtime by the FastAPI applications.

### k8s/deployment.yaml

Kubernetes Deployment manifest that defines how the Iris API application should be deployed in a Kubernetes cluster. It specifies 1 replica, container image from Google Artifact Registry, and exposes port 8200.

**Utility**: Manages the deployment of the containerized API in a Kubernetes environment, ensuring scalability and reliability.

### k8s/service.yaml

Kubernetes Service manifest that exposes the deployment as a LoadBalancer service on port 80, forwarding traffic to port 8200 on the pods.

**Utility**: Provides external access to the API through a stable endpoint, load balancing traffic across deployment replicas.

### .github/workflows/deploy.yaml

GitHub Actions workflow file that automates the CI/CD pipeline. It builds and pushes the Docker image to Google Artifact Registry, then deploys to GKE on pushes to the main branch.

**Utility**: Automates the deployment process, ensuring consistent and reliable releases to production environments with each code change.
