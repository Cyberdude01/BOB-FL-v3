# BOB-FL API Documentation

## Overview

This document provides detailed API documentation for the BOB-FL Flash Loan Execution System. The system includes several key components with their respective APIs:

1. **Execution Engine API** - For executing flash loan opportunities
2. **Pattern Recognition API** - For identifying and managing opportunity patterns
3. **Performance Monitoring API** - For tracking system performance
4. **Dashboard API** - For real-time metrics and monitoring

## 1. Execution Engine API

### Phase3ExecutionEngine

The core execution engine that handles flash loan opportunities across multiple networks.

#### Methods

##### `async execute_opportunity(opportunity: Opportunity, network: str) -> ExecutionResult`

Executes a flash loan opportunity on the specified network.

**Parameters:**
- `opportunity` (Opportunity): The opportunity to execute
- `network` (str): Target blockchain network ('arbitrum', 'base', 'ethereum', 'optimism', 'cross_chain')

**Returns:**
- `ExecutionResult`: Result object containing execution details

**Example:**
```python
from phase3_execution_system import Opportunity
from datetime import datetime, timezone

opportunity = Opportunity(
    id="test_opportunity",
    timestamp=datetime.now(timezone.utc),
    estimated_profit_usd=1500.0,
    liquidity_usd=100000.0,
    confidence_score=0.85,
    protocol="aave",
    token_pair="USDC-USDT",
    network="arbitrum"
)

result = await engine.execute_opportunity(opportunity, "arbitrum")
```

##### `get_metrics() -> Dict[str, Any]`

Returns current performance metrics.

**Returns:**
- `Dict[str, Any]`: Metrics dictionary with keys:
  - `total_attempts`: Total number of execution attempts
  - `successful_executions`: Number of successful executions
  - `failed_executions`: Number of failed executions
  - `average_execution_time`: Average execution time in seconds
  - `total_profit`: Total profit from successful executions

##### `get_network_config(network: str) -> Optional[Dict[str, Any]]`

Returns configuration for a specific network.

**Parameters:**
- `network` (str): Network name

**Returns:**
- `Dict[str, Any]` or `None`: Network configuration or None if not found

## 2. Pattern Recognition API

### PatternRecognizer

Identifies patterns in flash loan opportunities.

#### Methods

##### `identify(opportunity: Opportunity) -> str`

Identifies a pattern for the given opportunity.

**Parameters:**
- `opportunity` (Opportunity): The opportunity to analyze

**Returns:**
- `str`: Pattern name ('vault_yield', 'cross_chain', 'emissions', 'liquidity', 'unknown')

**Example:**
```python
pattern = recognizer.identify(opportunity)
print(f"Identified pattern: {pattern}")
```

### PatternPlaybooks

Manages execution playbooks for different patterns.

#### Methods

##### `get_playbook(pattern: str, opportunity: Opportunity) -> Optional[PatternPlaybook]`

Returns a playbook for the specified pattern.

**Parameters:**
- `pattern` (str): Pattern name
- `opportunity` (Opportunity): The opportunity to create playbook for

**Returns:**
- `PatternPlaybook` or `None`: Playbook object or None if pattern not found

**Example:**
```python
playbook = pattern_playbooks.get_playbook('vault_yield', opportunity)
if playbook:
    print(f"Playbook steps: {playbook.steps}")
    print(f"Estimated time: {playbook.estimated_time}s")
    print(f"Success rate: {playbook.success_rate}")
```

## 3. Performance Monitoring API

### PerformanceMonitor

Tracks and analyzes system performance metrics.

#### Methods

##### `track(detection_time: float, execution_time: float, opportunity_profit: float, success: bool)`

Tracks a new execution attempt.

**Parameters:**
- `detection_time` (float): Time taken to detect opportunity (seconds)
- `execution_time` (float): Time taken to execute opportunity (seconds)
- `opportunity_profit` (float): Estimated profit from opportunity
- `success` (bool): Whether execution was successful

##### `summary() -> Dict[str, Any]`

Returns performance summary.

**Returns:**
- `Dict[str, Any]`: Summary with keys:
  - `total_attempts`: Total number of attempts
  - `successes`: Number of successful attempts
  - `success_rate`: Success rate as decimal
  - `average_detection_seconds`: Average detection time
  - `average_execution_seconds`: Average execution time
  - `average_profit_per_success`: Average profit per successful execution
  - `total_profit`: Total profit from successful executions

**Example:**
```python
monitor.track(2.0, 0.8, 1500.0, True)
monitor.track(12.5, 0.9, 1200.0, True)
monitor.track(30.0, 2.0, 0.0, False)

summary = monitor.summary()
print(f"Success rate: {summary['success_rate']:.0%}")
print(f"Average profit: ${summary['average_profit_per_success']:.2f}")
```

## 4. Dashboard API

### HTTP Endpoints

The dashboard server provides REST API endpoints for real-time metrics access.

#### Base URL
`http://localhost:8080`

#### Endpoints

##### `GET /api/summary`

Returns system summary metrics.

**Response:**
```json
{
  "total_attempts": 5,
  "successes": 5,
  "failures": 0,
  "avg_detection_latency": 0.002,
  "avg_execution_latency": 1.392,
  "total_profit": 6700.0,
  "success_rate": 1.0
}
```

##### `GET /api/executions`

Returns recent execution history.

**Response:**
```json
{
  "recent_executions": [
    {
      "id": 1,
      "timestamp": "2026-05-21T12:00:00.000Z",
      "network": "arbitrum",
      "opportunity_id": "test_opportunity",
      "detection_latency": 2.0,
      "execution_latency": 0.8,
      "profit": 1500.0,
      "success": true,
      "pattern": "vault_yield",
      "playbook": "vault_yield"
    }
  ]
}
```

##### `GET /api/patterns`

Returns recent pattern recognition logs.

**Response:**
```json
{
  "recent_patterns": [
    {
      "id": 1,
      "timestamp": "2026-05-21T12:00:00.000Z",
      "network": "arbitrum",
      "opportunity_id": "test_opportunity",
      "pattern": "vault_yield",
      "details": {
        "protocol": "aave",
        "token_pair": "USDC-USDT"
      }
    }
  ]
}
```

##### `GET /health`

Returns server health status.

**Response:**
```json
{
  "status": "ok",
  "timestamp": 1716384000.123
}
```

#### cURL Examples

```bash
# Get summary metrics
curl http://localhost:8080/api/summary

# Get recent executions
curl http://localhost:8080/api/executions

# Get recent patterns
curl http://localhost:8080/api/patterns

# Health check
curl http://localhost:8080/health
```

## 5. Data Storage API

### MetricsStore

Manages persistent storage for metrics and patterns.

#### Methods

##### `record_execution(record: ExecutionMetricRecord)`

Records an execution metric.

**Parameters:**
- `record` (ExecutionMetricRecord): Execution metric record

##### `record_pattern(record: PatternRecord)`

Records a pattern recognition.

**Parameters:**
- `record` (PatternRecord): Pattern recognition record

##### `recent_executions(limit: int = 25) -> List[Dict[str, Any]]`

Returns recent execution records.

**Parameters:**
- `limit` (int): Maximum number of records to return

**Returns:**
- `List[Dict[str, Any]]`: List of execution records

##### `recent_patterns(limit: int = 25) -> List[Dict[str, Any]]`

Returns recent pattern recognition records.

**Parameters:**
- `limit` (int): Maximum number of records to return

**Returns:**
- `List[Dict[str, Any]]`: List of pattern records

##### `summary() -> Dict[str, Any]`

Returns storage summary.

**Returns:**
- `Dict[str, Any]`: Summary of stored data

##### `export_snapshot() -> Dict[str, Any]`

Exports a complete system snapshot.

**Returns:**
- `Dict[str, Any]`: Complete system snapshot

## 6. Production Controls API

### ProductionGate

Manages deployment and risk controls.

#### Methods

##### `can_deploy(forecast_profit: float, forecast_risk: float, failures: int) -> bool`

Evaluates if deployment is allowed.

**Parameters:**
- `forecast_profit` (float): Expected profit from deployment
- `forecast_risk` (float): Risk assessment (0.0-1.0)
- `failures` (int): Number of recent failures

**Returns:**
- `bool`: True if deployment is allowed

##### `deploy(version: DeploymentVersion)`

Deploys a new version.

**Parameters:**
- `version` (DeploymentVersion): Version to deploy

##### `canary(version: DeploymentVersion) -> bool`

Performs canary deployment.

**Parameters:**
- `version` (DeploymentVersion): Version to canary deploy

**Returns:**
- `bool`: True if canary deployment succeeded

##### `record_rollback(reason: str)`

Records a rollback event.

**Parameters:**
- `reason` (str): Reason for rollback

## 7. Configuration API

### Environment Variables

The system uses environment variables for configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `INFURA_API_KEY` | Infura API key | Required |
| `FLASHBOTS_API_KEY` | Flashbots API key | Required |
| `EDEN_API_KEY` | Eden Network API key | Required |
| `DATABASE_PATH` | Database file path | `./data/flash_loan_metrics.db` |
| `DASHBOARD_HOST` | Dashboard server host | `0.0.0.0` |
| `DASHBOARD_PORT` | Dashboard server port | `8080` |
| `MAX_DAILY_LOSS_USD` | Maximum daily loss limit | `10000` |
| `MAX_CONSECUTIVE_FAILURES` | Maximum consecutive failures | `5` |
| `MIN_SUCCESS_RATE` | Minimum success rate | `0.8` |
| `DETECTION_TARGET_MINUTES` | Detection target window | `13` |
| `EXECUTION_TARGET_SECONDS` | Execution target time | `60` |
| `BUNDLE_TARGET_SECONDS` | Bundle submission target | `10` |

### Configuration Files

#### api-keys-config.json
```json
{
  "infura": "your_infura_api_key",
  "flashbots": "your_flashbots_api_key",
  "eden": "your_eden_api_key",
  "the_graph": "your_graph_api_key"
}
```

#### research-config.json
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
    }
  },
  "protocols": {
    "aave": {
      "lending_pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD"
    }
  }
}
```

## 8. Error Handling

### Common Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| `unsupported_network` | Network not supported | Check network name spelling |
| `opportunity_validation_failed` | Opportunity validation failed | Check profit, confidence, liquidity thresholds |
| `risk_evaluation_failed` | Risk evaluation failed | Check risk policy constraints |
| `execution_failed` | Execution failed | Check network connectivity and API keys |
| `database_error` | Database operation failed | Check database file permissions |
| `dashboard_server_error` | Dashboard server failed | Check port availability |

### Error Response Format

```json
{
  "error": "error_description",
  "error_code": "error_code",
  "timestamp": "2026-05-21T12:00:00.000Z",
  "details": {
    "additional_context": "error_details"
  }
}
```

## 9. Rate Limiting

The API implements rate limiting to prevent abuse:

- **Dashboard API**: 100 requests per minute per IP
- **Execution Engine**: 10 requests per second per network
- **Pattern Recognition**: 50 requests per minute per IP

Rate limit headers are included in responses:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 99
X-RateLimit-Reset: 1716384000
```

## 10. Authentication

Currently, the system uses API key authentication via environment variables. Future versions may implement:

- JWT tokens for API access
- OAuth 2.0 for third-party integrations
- IP whitelisting for restricted access

---

For additional support or questions, please refer to the main documentation or create an issue on GitHub.