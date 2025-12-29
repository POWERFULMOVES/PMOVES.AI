# TensorZero Configuration Management

**Dynamic configuration management for TensorZero LLM Gateway with validation, observability, and hot-reload capabilities.**

## Overview

TensorZero Configuration Management provides a complete toolkit for managing LLM gateway configurations dynamically, without requiring service restarts. This system handles configuration validation, change tracking, and observability for production deployments.

## Features

### Core Library (`tz_config`)
- **TOML Parser**: Parse and validate TensorZero configuration files
- **JSON Schema Validation**: Structural validation against comprehensive schema
- **Semantic Validation**: Cross-reference checking (models, functions, variants)
- **Hot Reload**: Apply configuration changes without service restart
- **ClickHouse Logging**: Audit trail of all configuration changes

### CLI Tool (`tz-cli`)
- **Validate**: Check configuration syntax and semantics
- **Add Variant**: Dynamically add new function variants
- **Apply Template**: Apply predefined templates to functions
- **Config Diff**: View changes between configurations
- **Hot Reload**: Trigger configuration reload on running gateway

### REST API (`tensorzero-config-api`)
- **GET /config**: Retrieve current configuration
- **POST /config/validate**: Validate configuration without applying
- **POST /config/reload**: Trigger hot reload of configuration
- **GET /history**: Retrieve configuration change history
- **GET /health**: API health check

### React UI (`tensorzero-config-ui`)
- **Configuration Editor**: Visual TOML editor with syntax highlighting
- **Validation Panel**: Real-time validation feedback
- **Change History**: Audit trail with diffs
- **Metrics Dashboard**: Validation error rates, hot reload success rates

## Installation

### Core Library

```bash
cd pmoves-agent-tz-core
pip install -e .
```

### CLI Tool

```bash
cd pmoves-agent-tz-cli
pip install -e .
```

### REST API

```bash
cd pmoves-agent-tz-obs
pip install -e .
```

### React UI

```bash
cd pmoves-agent-tz-ui
npm install
npm run build
```

## Configuration Schema

TensorZero configurations use TOML format with the following structure:

```toml
[gateway.observability]
enabled = true
async_writes = true

# Model configuration with provider routing
[models.gpt4]
routing = ["openai"]

[models.gpt4.providers.openai]
type = "openai"
api_base = "https://api.openai.com/v1"
model_name = "gpt-4"
api_key_location = "env::OPENAI_API_KEY"

# Function definitions with variants
[functions.chat]
type = "chat"

[functions.chat.variants.primary]
type = "chat_completion"
model = "gpt4"
weight = 1.0

[functions.chat.variants.fallback]
type = "chat_completion"
model = "gpt35"
weight = 0.5

# Embedding models
[embedding_models.default]
provider = "openai"
api_base = "https://api.openai.com/v1"
model = "text-embedding-3-small"

# Tools (optional)
[tools.search]
type = "wrapper"
endpoint = "http://localhost:8080/search"
```

## Validation Rules

### Identifier Names
- Must start with a letter
- May contain alphanumeric characters, underscores, and hyphens
- Pattern: `^[a-zA-Z][a-zA-Z0-9_-]*$`

### Model Configuration
- At least one provider required
- Provider type must be one of: `openai`, `anthropic`, `vertex`, `custom`
- `api_base` must be a valid URI
- Routing arrays must reference existing providers

### Function Variants
- Must reference an existing model or embedding model
- Weight must be a positive number
- Variant type must match function type

### Cross-References
- All model references in variants must exist
- All embedding model references must exist
- No circular dependencies allowed

## Observability

Configuration changes are logged to ClickHouse for audit and analysis:

```sql
-- Query change history
SELECT
    timestamp,
    author,
    change_type,
    resource_type,
    resource_name,
    validation_result
FROM tensorzero_config_changes
ORDER BY timestamp DESC
LIMIT 100;

-- Calculate validation error rate (last 24 hours)
SELECT
    countIf(validation_result = 0) AS errors,
    count(*) AS total,
    (errors / total) * 100 AS error_rate
FROM tensorzero_config_changes
WHERE timestamp >= now() - INTERVAL 1 DAY;

-- Count rollbacks (last 24 hours)
SELECT count(*)
FROM tensorzero_config_changes
WHERE change_type = 'rollback'
AND timestamp >= now() - INTERVAL 1 DAY;
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/config` | Retrieve current configuration |
| POST | `/config/validate` | Validate configuration without applying |
| POST | `/config/reload` | Trigger hot reload |
| GET | `/history` | Retrieve change history |
| GET | `/health` | Health check |

### Example: Validate Configuration

```bash
curl -X POST http://localhost:8081/config/validate \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "models": {
        "gpt4": {
          "providers": {
            "openai": {
              "type": "openai",
              "api_base": "https://api.openai.com/v1",
              "model_name": "gpt-4"
            }
          }
        }
      }
    }
  }'
```

### Example: Trigger Hot Reload

```bash
curl -X POST http://localhost:8081/config/reload \
  -H "Content-Type: application/json" \
  -d '{"author": "cli-user"}'
```

## CLI Usage

### Validate Configuration

```bash
# Validate default config
tz-cli validate

# Validate specific file
tz-cli validate /path/to/tensorzero.toml
```

### Add Function Variant

```bash
tz-cli add_variant chat experimental \
  --model gpt4 \
  --weight 0.8
```

### Apply Template

```bash
# Apply predefined template to function
tz-cli apply_template rag_search chat
```

### View Configuration Diff

```bash
tz-cli diff current.toml previous.toml
```

## Development

### Running Tests

```bash
# Core library tests
cd pmoves-agent-tz-core
pytest tests/

# CLI tests
cd pmoves-agent-tz-cli
pytest tests/

# API tests
cd pmoves-agent-tz-obs
pytest tests/
```

### Code Quality

```bash
# Type checking
mypy pmoves/libs/tz_config/

# Linting
ruff check pmoves/libs/tz_config/

# Formatting
ruff format pmoves/libs/tz_config/
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TensorZero Gateway                        │
│                    (tensorzero.toml)                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  Config Change Logger                        │
│                    (ClickHouse)                              │
└─────────────────────────────────────────────────────────────┘

         ┌─────────────────┬─────────────────┬──────────────┐
         ▼                 ▼                 ▼              ▼
   ┌─────────┐       ┌─────────┐       ┌─────────┐   ┌─────────┐
   │   CLI   │       │  REST   │       │  React  │   │  Hot    │
   │   Tool  │       │   API   │       │   UI    │   │ Reload  │
   └─────────┘       └─────────┘       └─────────┘   └─────────┘
```

## Security Considerations

### Path Validation
- All file paths are validated for traversal attacks
- Only `.toml` extensions allowed for configurations
- Paths are resolved relative to safe base directories

### SQL Injection Prevention
- All SQL identifiers (table/database names) are validated
- Parameterized queries used for all values
- Backtick quoting for validated identifiers

### Input Validation
- All user inputs validated against regex patterns
- JSON schema validation for structural integrity
- Cross-reference validation prevents injection via references

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

Proprietary - Copyright (c) 2024 POWERFULMOVES

## Support

For issues and questions, please use the PMOVES.AI issue tracker.
