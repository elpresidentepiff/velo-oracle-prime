# VÉLØ Shadow Race Engine - Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the VÉLØ Shadow Race Engine to staging and production environments.

## Prerequisites

### System Requirements
- Docker 20.10+
- Docker Compose 2.0+
- Kubernetes 1.20+ (for production)
- Access to cloud provider (AWS, GCP, Azure)
- CI/CD pipeline configured

### Access Requirements
- Repository access (read/write)
- Cloud provider access
- Secrets management access
- Monitoring system access

## Deployment Strategy

### Blue-Green Deployment

**Strategy:**
1. Deploy new version to green environment
2. Run integration tests
3. Switch traffic from blue to green
4. Monitor for issues
5. Rollback if needed

**Benefits:**
- Zero downtime
- Easy rollback
- Reduced risk

### Canary Deployment

**Strategy:**
1. Deploy to small subset of users
2. Monitor performance and accuracy
3. Gradually increase traffic
4. Full deployment if successful

**Benefits:**
- Early issue detection
- Reduced blast radius
- Controlled rollout

## Staging Deployment

### Step 1: Prepare Staging Environment

```bash
# Clone repository
git clone https://github.com/velo-oracle-prime.git
cd velo-oracle-prime

# Create staging branch
git checkout -b staging/deploy-$(date +%Y%m%d)

# Install dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set environment variables
export VELO_ENVIRONMENT=staging
export DATABASE_URL=${{ secrets.STAGING_DATABASE_URL }}
export API_KEY=${{ secrets.STAGING_API_KEY }}
```

### Step 2: Run Pre-Deployment Tests

```bash
# Run unit tests
python -m pytest test/ -v

# Run shadow race test suite
python test/shadow_race_test_suite.py

# Check accuracy threshold
python -c "
import json
from pathlib import Path
report_path = Path('shadow_race_simulations/test_suite_report.json')
with open(report_path, 'r') as f:
    report = json.load(f)
accuracy = report['results']['accuracy']
if accuracy >= 0.6:
    print('✅ Pre-deployment tests passed')
else:
    print(f'❌ Pre-deployment tests failed: {accuracy:.2%}')
    exit(1)
"
```

### Step 3: Build Docker Image

```bash
# Build image
docker build -t velo-shadow-race:staging-${{ github.sha }} .

# Tag image
docker tag velo-shadow-race:staging-${{ github.sha }} registry.velo.com/velo-shadow-race:staging

# Push to registry
docker push registry.velo.com/velo-shadow-race:staging
```

### Step 4: Deploy to Staging

```bash
# Deploy with Docker Compose
docker-compose -f docker-compose.staging.yml up -d

# Check deployment status
docker-compose -f docker-compose.staging.yml ps

# View logs
docker-compose -f docker-compose.staging.yml logs -f
```

### Step 5: Run Integration Tests

```bash
# Wait for service to be ready
sleep 30

# Run integration tests
python -m pytest test/integration/ -v

# Test API endpoints
curl -X GET http://staging.velo.com:8000/health

# Test shadow race endpoint
curl -X POST http://staging.velo.com:8000/shadow-race \
  -H "Content-Type: application/json" \
  -d @test_data/sample_race.json
```

### Step 6: Validate Deployment

```bash
# Check metrics
curl http://staging.velo.com:8000/metrics

# Check accuracy
python -c "
import requests
response = requests.get('http://staging.velo.com:8000/metrics')
print(response.text)
"

# Monitor for 1 hour
sleep 3600

# Check logs for errors
docker-compose -f docker-compose.staging.yml logs --tail=100
```

### Step 7: Promote to Production

```bash
# If validation passes, promote to production
git tag staging/v1.0.0
git push origin staging/v1.0.0

# Merge to main
git checkout main
git merge staging/deploy-$(date +%Y%m%d)
git push origin main
```

## Production Deployment

### Step 1: Prepare Production Environment

```bash
# Switch to production branch
git checkout main

# Pull latest changes
git pull origin main

# Set production environment variables
export VELO_ENVIRONMENT=production
export DATABASE_URL=${{ secrets.PRODUCTION_DATABASE_URL }}
export API_KEY=${{ secrets.PRODUCTION_API_KEY }}
export SLACK_WEBHOOK_URL=${{ secrets.SLACK_WEBHOOK_URL }}
```

### Step 2: Run Final Validation

```bash
# Run all tests
python -m pytest test/ -v
python test/shadow_race_test_suite.py

# Check accuracy threshold
python -c "
import json
from pathlib import Path
report_path = Path('shadow_race_simulations/test_suite_report.json')
with open(report_path, 'r') as f:
    report = json.load(f)
accuracy = report['results']['accuracy']
if accuracy >= 0.6:
    print('✅ Final validation passed')
else:
    print(f'❌ Final validation failed: {accuracy:.2%}')
    exit(1)
"

# Security scan
python -m bandit -r . -f json -o security_scan.json
```

### Step 3: Build Production Image

```bash
# Build production image
docker build -t velo-shadow-race:production-${{ github.sha }} .

# Tag production image
docker tag velo-shadow-race:production-${{ github.sha }} registry.velo.com/velo-shadow-race:production

# Push to production registry
docker push registry.velo.com/velo-shadow-race:production
```

### Step 4: Deploy to Production (Blue-Green)

```bash
# Deploy green environment
docker-compose -f docker-compose.production.yml up -d velo-shadow-race-green

# Wait for green to be ready
sleep 60

# Run smoke tests on green
curl -X GET http://production.velo.com:8001/health

# Switch traffic from blue to green
# (This would be done via load balancer configuration)

# Monitor green environment
sleep 300  # 5 minutes

# Check for errors
if docker-compose -f docker-compose.production.yml logs velo-shadow-race-green | grep -i error; then
    echo "❌ Errors detected, rolling back"
    exit 1
fi

# If successful, stop blue environment
docker-compose -f docker-compose.production.yml stop velo-shadow-race-blue

# Tag release
git tag production/v1.0.0
git push origin production/v1.0.0
```

### Step 5: Post-Deployment Monitoring

```bash
# Monitor for 24 hours
for i in {1..24}; do
    echo "Hour $i of 24"
    
    # Check health
    curl -s http://production.velo.com:8000/health | jq .
    
    # Check metrics
    curl -s http://production.velo.com:8000/metrics | grep velo_shadow_race_accuracy
    
    # Check logs for errors
    docker-compose -f docker-compose.production.yml logs --tail=100 velo-shadow-race-green | grep -i error
    
    sleep 3600
done

# Final validation
echo "✅ Production deployment successful"
```

## Kubernetes Deployment

### Step 1: Create Kubernetes Manifests

**Location:** `/k8s/`

**deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: velo-shadow-race
  namespace: velo-production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: velo-shadow-race
  template:
    metadata:
      labels:
        app: velo-shadow-race
    spec:
      containers:
      - name: velo-shadow-race
        image: registry.velo.com/velo-shadow-race:production
        ports:
        - containerPort: 8000
        env:
        - name: VELO_ENVIRONMENT
          value: "production"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: velo-secrets
              key: database-url
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

**service.yaml:**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: velo-shadow-race
  namespace: velo-production
spec:
  selector:
    app: velo-shadow-race
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

**ingress.yaml:**
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: velo-shadow-race
  namespace: velo-production
  annotations:
    kubernetes.io/ingress.class: "nginx"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - api.velo.com
    secretName: velo-tls
  rules:
  - host: api.velo.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: velo-shadow-race
            port:
              number: 80
```

### Step 2: Deploy to Kubernetes

```bash
# Apply manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# Check deployment status
kubectl get pods -n velo-production
kubectl get services -n velo-production
kubectl get ingress -n velo-production

# View logs
kubectl logs -f deployment/velo-shadow-race -n velo-production
```

### Step 3: Configure Autoscaling

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: velo-shadow-race-hpa
  namespace: velo-production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: velo-shadow-race
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

```bash
kubectl apply -f k8s/hpa.yaml
```

## Rollback Procedures

### Immediate Rollback (Critical Issues)

```bash
# If errors detected during deployment

# For Docker Compose:
docker-compose -f docker-compose.production.yml stop velo-shadow-race-green
docker-compose -f docker-compose.production.yml start velo-shadow-race-blue

# For Kubernetes:
kubectl rollout undo deployment/velo-shadow-race -n velo-production
```

### Gradual Rollback (Performance Issues)

```bash
# Reduce traffic gradually
# Update load balancer weights
# Monitor metrics
# If issues persist, full rollback
```

## Monitoring and Alerting

### Key Metrics to Monitor

1. **Accuracy:**
   - Target: ≥ 60% (shadow), ≥ 65% (live)
   - Alert if: < 50% for 10 consecutive races

2. **RIC+ Validation:**
   - Target: ≥ 95% pass rate
   - Alert if: < 90% pass rate

3. **Performance:**
   - Target: < 5 seconds latency
   - Alert if: > 10 seconds latency

4. **Error Rate:**
   - Target: < 1% error rate
   - Alert if: > 5% error rate

### Alert Configuration

```yaml
# config/alert-rules.yml
groups:
  - name: velo-production
    rules:
      - alert: ProductionAccuracyLow
        expr: velo_shadow_race_accuracy < 0.5
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Production accuracy below 50%"
          description: "Current accuracy: {{ $value }}"
          
      - alert: HighErrorRate
        expr: rate(velo_errors_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Error rate above 5%"
```

## Cost Optimization

### Infrastructure Costs

**Staging:**
- Compute: $100/month
- Database: $50/month
- Storage: $20/month
- Total: ~$170/month

**Production:**
- Compute: $500/month (auto-scaling)
- Database: $200/month
- Storage: $50/month
- Monitoring: $100/month
- Total: ~$850/month

### Optimization Strategies

1. **Auto-scaling:** Scale down during off-peak hours
2. **Spot Instances:** Use for non-critical workloads
3. **Reserved Instances:** Commit to 1-year for production
4. **Data Archiving:** Archive old logs to cold storage
5. **Cache Optimization:** Use Redis for frequent queries

## Security Checklist

### Pre-Deployment
- [ ] All secrets encrypted
- [ ] API keys rotated
- [ ] Security scan passed
- [ ] Vulnerability scan passed
- [ ] Access controls configured

### Post-Deployment
- [ ] SSL certificates valid
- [ ] Firewall rules configured
- [ ] Logging enabled
- [ ] Audit trail active
- [ ] Backup system tested

## Disaster Recovery

### Recovery Time Objective (RTO): 1 hour
### Recovery Point Objective (RPO): 15 minutes

### Recovery Procedures

**Scenario 1: Database Failure**
1. Restore from latest backup
2. Replay transaction logs
3. Validate data integrity
4. Switch application to restored DB

**Scenario 2: Application Failure**
1. Deploy from last known good version
2. Restore from backup if needed
3. Validate functionality
4. Monitor for issues

**Scenario 3: Infrastructure Failure**
1. Failover to secondary region
2. Update DNS records
3. Validate service restoration
4. Investigate root cause

## Success Criteria

### Deployment Complete When:

- ✅ All tests passing
- ✅ Accuracy ≥ 60% (shadow) / ≥ 65% (live)
- ✅ RIC+ validation ≥ 95%
- ✅ Performance < 5 seconds
- ✅ Error rate < 1%
- ✅ Monitoring active
- ✅ Alerts configured
- ✅ Documentation updated
- ✅ Team notified

## Post-Deployment Tasks

1. **Documentation:**
   - Update deployment records
   - Document lessons learned
   - Update runbooks

2. **Team Communication:**
   - Notify stakeholders
   - Share metrics
   - Schedule review meeting

3. **Continuous Improvement:**
   - Review performance
n   - Identify bottlenecks
   - Plan next iteration

## References

- VÉLØ Master Doctrine: /docs/agent_zero/00_role_and_mindset.md
- Shadow Race Protocol: /docs/agent_zero/08_testing_shadow_races_protocol.md
- Fail-Safe Guide: /docs/agent_zero/09_fail_safes_and_no_guess_sentinel.md
- Integration Guide: /docs/integration_guide.md
- CI/CD Config: /.github/workflows/shadow-race-tests.yml
- Docker Compose: /docker-compose.yml
- Kubernetes Manifests: /k8s/

---

**Document Version:** 1.0  
**Last Updated:** 2025-01-22  
**Author:** Commander Zero  
**Status:** Active
