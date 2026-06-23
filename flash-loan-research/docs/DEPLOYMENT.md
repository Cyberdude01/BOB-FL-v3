# BOB-FL Deployment Documentation

## Overview

This document provides comprehensive deployment instructions for the BOB-FL Flash Loan Execution System. The deployment process covers setting up the environment, configuring the system, and running in production.

## Prerequisites

### System Requirements

- **Operating System**: Ubuntu 20.04+ / CentOS 8+ / macOS 10.15+
- **Python**: 3.8 or higher
- **Memory**: Minimum 8GB RAM (16GB recommended)
- **Storage**: Minimum 50GB SSD (100GB recommended)
- **Network**: Stable internet connection with low latency

### Software Dependencies

- **Git**: For version control
- **Python 3.8+**: Runtime environment
- **pip**: Python package manager
- **Virtual Environment**: Recommended for isolation

### Infrastructure Requirements

- **Database**: SQLite (included) or PostgreSQL (for production)
- **Web Server**: Python HTTP server (included) or Nginx (for production)
- **Monitoring**: Built-in dashboard or external monitoring tools
- **Backup**: Regular backup strategy

## Deployment Process

### Step 1: Environment Setup

#### 1.1 Clone the Repository

```bash
git clone https://github.com/Cyberdude01/BOB-FL.git
cd BOB-FL
```

#### 1.2 Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### 1.3 Install Dependencies

```bash
pip install -r requirements.txt
pip install -e .
```

#### 1.4 Verify Installation

```bash
# Test basic functionality
python phase3_demo.py
python phase4_demo.py
python phase56_integrated_workflow.py
```

### Step 2: Configuration

#### 2.1 Environment Variables

Create a `.env` file from the template:

```bash
cp .env.example .env
```

Edit the `.env` file with your configuration:

```bash
# API Keys
INFURA_API_KEY=
FLASHBOTS_API_KEY=
EDEN_API_KEY=your_eden_api_key_here
GRAPH_API_KEY=your_graph_api_key_here

# Database
DATABASE_PATH=./data/flash_loan_metrics.db

# Dashboard
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8080

# Risk Configuration
MAX_DAILY_LOSS_USD=10000
MAX_CONSECUTIVE_FAILURES=5
MIN_SUCCESS_RATE=0.8

# Time Configuration
DETECTION_TARGET_MINUTES=13
EXECUTION_TARGET_SECONDS=60
BUNDLE_TARGET_SECONDS=10
```

#### 2.2 API Keys Configuration

Create and configure `api-keys-config.json`:

```bash
cp api-keys-config.example.json api-keys-config.json
```

```json
{
  "infura": "your_infura_api_key",
  "flashbots": "your_flashbots_api_key",
  "eden": "your_eden_api_key",
  "the_graph": "your_graph_api_key"
}
```

#### 2.3 Network Configuration

Update network configurations in `research-config.json`:

```json
{
  "networks": {
    "arbitrum": {
      "rpc": "https://arb1.arbitrum.io/rpc",
      "chain_id": 42161
    },
    "base": {
      "rpc": "https://mainnet.base.org",
      "chain_id": 8453
    },
    "ethereum": {
      "rpc": "https://mainnet.infura.io/v3/YOUR_KEY",
      "chain_id": 1
    },
    "optimism": {
      "rpc": "https://mainnet.optimism.io",
      "chain_id": 10
    }
  },
  "protocols": {
    "aave": {
      "lending_pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD"
    },
    "uniswap": {
      "factory": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"
    }
  }
}
```

### Step 3: Database Setup

#### 3.1 Initialize Database

```bash
python -c "from phase5_data_store import MetricsStore; MetricsStore().init_db()"
```

#### 3.2 Verify Database

```bash
ls -la phase5_metrics.db
# Should show the database file
```

#### 3.3 Create Backup Directory

```bash
mkdir -p backups
mkdir -p logs
mkdir -p data/replica
```

### Step 4: System Configuration

#### 4.1 Risk Policy Configuration

Edit the risk policy in `phase6_production_controls.py`:

```python
risk_policy = RiskPolicy(
    max_daily_loss_usd=10000.0,
    max_consecutive_failures=5,
    min_success_rate=0.8
)
```

#### 4.2 Time Configuration

Update timeframe configuration in `phase5_optimization.py`:

```python
timeframe_config = TimeframeConfig()
timeframe_config.update(
    detection_target_min=13,
    execution_target_seconds=60,
    bundle_target_seconds=10
)
```

### Step 5: Production Deployment

#### 5.1 Start the Dashboard Server

```bash
# Start dashboard in background
nohup python phase5_dashboard_server.py > logs/dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo "Dashboard server started with PID: $DASHBOARD_PID"
```

#### 5.2 Start the Execution Engine

```bash
# Start execution engine in background
nohup python phase56_integrated_workflow.py > logs/execution.log 2>&1 &
EXECUTION_PID=$!
echo "Execution engine started with PID: $EXECUTION_PID"
```

#### 5.3 Verify Services

```bash
# Check dashboard
curl http://localhost:8080/health

# Check execution engine
ps aux | grep phase56_integrated_workflow.py
```

### Step 6: Monitoring and Maintenance

#### 6.1 System Monitoring

```bash
# Monitor dashboard logs
tail -f logs/dashboard.log

# Monitor execution logs
tail -f logs/execution.log

# Check system resources
htop
df -h
```

#### 6.2 Performance Metrics

```bash
# Get dashboard metrics
curl http://localhost:8080/api/summary

# Get recent executions
curl http://localhost:8080/api/executions

# Get patterns
curl http://localhost:8080/api/patterns
```

#### 6.3 Backup Strategy

```bash
# Create backup
./flash-loan-backup-$(date +%Y%m%d-%H%M%S).tar.gz

# Database backup
cp phase5_metrics.db backups/phase5_metrics_$(date +%Y%m%d).db

# Configuration backup
cp .env api-keys-config.json research-config.json backups/
```

## Production Deployment Options

### Option 1: Direct Deployment

Simple deployment for single-node setups:

```bash
#!/bin/bash
# deploy.sh - Production deployment script

# Set up environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with production values

# Initialize database
python -c "from phase5_data_store import MetricsStore; MetricsStore().init_db()"

# Start services
nohup python phase5_dashboard_server.py > logs/dashboard.log 2>&1 &
nohup python phase56_integrated_workflow.py > logs/execution.log 2>&1 &

echo "Deployment completed!"
echo "Dashboard: http://localhost:8080"
echo "Health: curl http://localhost:8080/health"
```

### Option 2: Docker Deployment

Containerized deployment for better isolation:

#### 2.1 Create Dockerfile

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs data/replica backups

# Expose dashboard port
EXPOSE 8080

# Start the application
CMD ["python", "phase5_dashboard_server.py"]
```

#### 2.2 Build and Run

```bash
# Build Docker image
docker build -t bob-fl .

# Run container
docker run -d \
  --name bob-fl \
  -p 8080:8080 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/backups:/app/backups \
  bob-fl
```

### Option 3: Kubernetes Deployment

For production-grade orchestration:

#### 3.1 Kubernetes Configuration

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bob-fl
spec:
  replicas: 3
  selector:
    matchLabels:
      app: bob-fl
  template:
    metadata:
      labels:
        app: bob-fl
    spec:
      containers:
      - name: bob-fl
        image: bob-fl:latest
        ports:
        - containerPort: 8080
        env:
        - name: INFURA_API_KEY
          valueFrom:
            secretKeyRef:
              name: bob-fl-secrets
              key: infura-key
        volumeMounts:
        - name: data
          mountPath: /app/data
        - name: logs
          mountPath: /app/logs
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: bob-fl-data
      - name: logs
        persistentVolumeClaim:
          claimName: bob-fl-logs
```

#### 3.2 Apply Configuration

```bash
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
```

## Configuration Management

### Environment-Specific Configuration

#### Development
```bash
# .env.development
INFURA_API_KEY=dev_infura_key
FLASHBOTS_API_KEY=dev_flashbots_key
DASHBOARD_HOST=127.0.0.1
LOG_LEVEL=DEBUG
```

#### Staging
```bash
# .env.staging
INFURA_API_KEY=staging_infura_key
FLASHBOTS_API_KEY=staging_flashbots_key
DASHBOARD_HOST=0.0.0.0
LOG_LEVEL=INFO
```

#### Production
```bash
# .env.production
INFURA_API_KEY=prod_infura_key
FLASHBOTS_API_KEY=prod_flashbots_key
DASHBOARD_HOST=0.0.0.0
LOG_LEVEL=WARNING
```

### Configuration Management Best Practices

1. **Never commit sensitive data** to version control
2. **Use environment variables** for configuration
3. **Implement configuration validation** on startup
4. **Document all configuration options**
5. **Use configuration templates** for different environments

## Security Considerations

### API Key Management

1. **Store keys securely** using environment variables or secret management
2. **Rotate keys regularly** to minimize exposure
3. **Use different keys** for different environments
4. **Monitor key usage** for unauthorized access

### Network Security

1. **Use HTTPS** for dashboard access in production
2. **Implement firewall rules** to restrict access
3. **Use VPN** for remote access
4. **Monitor network traffic** for suspicious activity

### Data Security

1. **Encrypt sensitive data** at rest
2. **Use secure connections** for database access
3. **Implement access controls** for data access
4. **Regular security audits** and penetration testing

## Monitoring and Alerting

### Health Checks

```bash
# Dashboard health
curl http://localhost:8080/health

# System health
curl http://localhost:8080/api/summary

# Database health
python -c "from phase5_data_store import MetricsStore; print('Database OK')"
```

### Alerting Configuration

#### Email Alerts
```python
# Configure email alerts in production
EMAIL_ALERTS = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'username': 'your_email@gmail.com',
    'password': 'your_password',
    'recipients': ['admin@example.com'],
    'alerts': {
        'high_failure_rate': 0.5,
        'low_profit_rate': 100,
        'system_error': True
    }
}
```

#### Slack Alerts
```python
# Configure Slack alerts
SLACK_WEBHOOK = 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
SLACK_CHANNEL = '#alerts'
```

### Log Management

1. **Centralized logging** using ELK stack or similar
2. **Log rotation** to prevent disk space issues
3. **Log analysis** for troubleshooting and optimization
4. **Security logging** for audit purposes

## Performance Optimization

### System Tuning

#### Memory Management
```python
# Optimize memory usage
import gc
gc.collect()  # Force garbage collection
```

#### Database Optimization
```sql
-- Add indexes for better performance
CREATE INDEX idx_phase5_logs_network ON phase5_logs(network);
CREATE INDEX idx_phase5_logs_timestamp ON phase5_logs(timestamp);
```

#### Network Optimization
```python
# Use connection pooling
import aiohttp
connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
```

### Scaling Considerations

1. **Horizontal scaling**: Add more instances behind a load balancer
2. **Vertical scaling**: Increase resources on existing instances
3. **Database scaling**: Consider PostgreSQL for large datasets
4. **Caching**: Implement Redis for frequently accessed data

## Troubleshooting

### Common Issues

#### 1. Dashboard Server Not Starting
```bash
# Check port availability
netstat -tlnp | grep 8080

# Kill existing process
pkill -f phase5_dashboard_server.py

# Restart with logging
python phase5_dashboard_server.py
```

#### 2. Database Connection Issues
```bash
# Check database file
ls -la phase5_metrics.db

# Reinitialize database
rm phase5_metrics.db
python -c "from phase5_data_store import MetricsStore; MetricsStore().init_db()"
```

#### 3. API Key Issues
```bash
# Validate API keys
curl -H "Authorization: Bearer $INFURA_API_KEY" $INFURA_RPC

# Check API key configuration
cat .env
```

### Log Analysis

#### Dashboard Logs
```bash
# Monitor dashboard logs
tail -f logs/dashboard.log | grep -i error

# Analyze performance
grep "execution_time" logs/dashboard.log | awk '{sum+=$3; count++} END {print "Avg:", sum/count}'
```

#### Execution Logs
```bash
# Monitor execution logs
tail -f logs/execution.log | grep -i success

# Analyze success rate
grep "success:" logs/execution.log | awk '{sum+=$2; count++} END {print "Rate:", sum/count*100"%"}'
```

## Backup and Recovery

### Backup Strategy

#### Automated Backup Script
```bash
#!/bin/bash
# backup.sh - Automated backup script

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="backups"
DB_FILE="phase5_metrics.db"

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
cp $DB_FILE $BACKUP_DIR/${DB_FILE}_${DATE}

# Backup configuration
cp .env api-keys-config.json research-config.json $BACKUP_DIR/config_${DATE}.tar.gz

# Backup logs
tar -czf $BACKUP_DIR/logs_${DATE}.tar.gz logs/

echo "Backup completed: $BACKUP_DIR/${DB_FILE}_${DATE}"
```

#### Recovery Procedure
```bash
# Restore database
cp backups/phase5_metrics_20240101_120000.db phase5_metrics.db

# Restore configuration
tar -xzf backups/config_20240101_120000.tar.gz

# Restart services
pkill -f phase5_dashboard_server.py
pkill -f phase56_integrated_workflow.py
nohup python phase5_dashboard_server.py > logs/dashboard.log 2>&1 &
nohup python phase56_integrated_workflow.py > logs/execution.log 2>&1 &
```

## Maintenance Schedule

### Daily Tasks
- Check system health (`curl http://localhost:8080/health`)
- Monitor logs (`tail -f logs/dashboard.log`)
- Verify metrics (`curl http://localhost:8080/api/summary`)
- Check disk space (`df -h`)

### Weekly Tasks
- Create weekly backup
- Review performance metrics
- Update security patches
- Check API key expiration

### Monthly Tasks
- Full system review
- Performance optimization
- Security audit
- Documentation updates

## Conclusion

This deployment guide provides comprehensive instructions for deploying BOB-FL in production. Follow these steps to ensure a successful deployment and maintain optimal system performance.

For additional support or questions, please refer to the documentation or create an issue on GitHub.