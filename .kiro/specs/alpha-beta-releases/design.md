# Design Document

## Overview

This design implements alpha and beta release automation for the Boomberman add-on, along with enhanced configuration options for the new bot detection and GeoIP features. The solution extends the existing GitHub Actions workflow to support pre-release channels and updates the Home Assistant add-on configuration to expose user-configurable security settings.

## Architecture

### Release Workflow Architecture

The enhanced GitHub Actions workflow will maintain the existing production release functionality while adding two new pre-release channels:

- **Alpha Channel**: Triggered by pushes to `dev*` branches
- **Beta Channel**: Triggered by pushes to `release*` branches  
- **Production Channel**: Triggered by version tags (existing functionality)

### Configuration Architecture

The add-on configuration will be extended to support the new environment variables through Home Assistant's options system, with automatic template generation for the container environment.

## Components and Interfaces

### 1. GitHub Actions Workflow Enhancement

**File**: `.github/workflows/build.yaml` (in the base Boomberman repository)

The workflow will be modified to include conditional release creation based on branch patterns:

```yaml
release-alpha:
  name: Create Alpha Release
  needs: build
  if: startsWith(github.ref, 'refs/heads/dev')
  runs-on: ubuntu-latest
  
release-beta:
  name: Create Beta Release  
  needs: build
  if: startsWith(github.ref, 'refs/heads/release')
  runs-on: ubuntu-latest
```

**Key Design Decisions**:
- Use branch name patterns to determine release type
- Generate unique release names using branch name and timestamp
- Mark alpha/beta releases as pre-releases in GitHub
- Include changelog generation for all release types

### 2. Add-on Configuration Enhancement

**File**: `addon-boomberman/config.yaml`

The configuration will be extended with new options for bot detection and system settings:

```yaml
options:
  # Existing options
  "AI Enabled": false
  "Ollama URL": "http://<ollama-url-ip>:11434"
  "Ollama model": "llama3.2"
  
  # New bot detection options
  "Bot Detection Enabled": true
  "Bot Detection Threshold Suspicious": 30
  "Bot Detection Threshold High Risk": 70
  "Log Retention Days": 7
  
  # Geographic analysis
  "High Risk Countries": "CN,RU,KP,IR"
  "VPN Penalty Score": 20
  "Hosting Provider Penalty": 15
  
  # Whitelist configuration
  "Whitelist IPs": "127.0.0.1,::1"
  "Whitelist ASNs": ""
```

### 3. Environment Template Updates

**File**: `addon-boomberman/rootfs/templates/.env_template`

The template will be updated to include all new environment variables with proper templating:

```bash
# Enhanced bot detection
BOT_DETECTION_ENABLED={{.bot_detection_enabled}}
BOT_DETECTION_THRESHOLD_SUSPICIOUS={{.bot_detection_threshold_suspicious}}
BOT_DETECTION_THRESHOLD_HIGH_RISK={{.bot_detection_threshold_high_risk}}

# Geographic configuration  
BOT_DETECTION_HIGH_RISK_COUNTRIES={{.high_risk_countries}}
BOT_DETECTION_VPN_PENALTY={{.vpn_penalty_score}}
BOT_DETECTION_HOSTING_PENALTY={{.hosting_provider_penalty}}

# Whitelist configuration
BOT_DETECTION_WHITELIST_IPS={{.whitelist_ips}}
BOT_DETECTION_WHITELIST_ASNS={{.whitelist_asns}}

# System configuration
LOG_RETENTION_DAYS={{.log_retention_days}}
```

## Data Models

### Release Naming Convention

- **Alpha**: `alpha-{branch-name}-{timestamp}` (e.g., `alpha-dev-feature-20241201-143022`)
- **Beta**: `beta-{branch-name}-{timestamp}` (e.g., `beta-release-1.2-20241201-143022`)  
- **Production**: `v{version}` (existing, e.g., `v0.1.13`)

### Configuration Schema

The add-on schema will be extended to validate new configuration options:

```yaml
schema:
  # Existing schema
  "AI Enabled": "bool"
  "Ollama URL": "str"
  "Ollama model": "str"
  
  # New schema additions
  "Bot Detection Enabled": "bool"
  "Bot Detection Threshold Suspicious": "int(0,100)"
  "Bot Detection Threshold High Risk": "int(0,100)"
  "Log Retention Days": "int(1,365)"
  "High Risk Countries": "str"
  "VPN Penalty Score": "int(0,100)"
  "Hosting Provider Penalty": "int(0,100)"
  "Whitelist IPs": "str"
  "Whitelist ASNs": "str?"
```

## Error Handling

### Workflow Error Handling

- **Branch Detection Failures**: Workflow will skip release creation if branch pattern matching fails
- **Changelog Generation Failures**: Will create release with generic changelog if git log fails
- **Docker Build Failures**: Will prevent release creation (existing behavior)

### Configuration Validation

- **Invalid Thresholds**: Home Assistant will reject configurations with thresholds outside 0-100 range
- **Invalid Country Codes**: Will log warnings but allow configuration (graceful degradation)
- **Invalid IP Addresses**: Will validate IP format in whitelist configuration

## Testing Strategy

### Workflow Testing

1. **Branch Testing**: Create test branches with `dev-test` and `release-test` patterns
2. **Release Verification**: Verify that releases are created with correct pre-release flags
3. **Changelog Testing**: Verify changelog generation works for different branch scenarios
4. **Docker Integration**: Ensure Docker images are properly tagged for each release type

### Configuration Testing

1. **Schema Validation**: Test all new configuration options with valid and invalid values
2. **Template Generation**: Verify environment variables are properly templated
3. **Default Values**: Ensure sensible defaults are applied when options are not specified
4. **Upgrade Testing**: Test configuration migration from existing installations

### Integration Testing

1. **End-to-End**: Test complete workflow from branch push to release creation
2. **Add-on Installation**: Test add-on installation with new configuration options
3. **Environment Variable Propagation**: Verify new environment variables reach the container
4. **Backward Compatibility**: Ensure existing installations continue to work

## Implementation Considerations

### GitHub Actions Limitations

- Release creation is limited by GitHub API rate limits
- Branch name length affects release name length (GitHub has limits)
- Pre-release flags cannot be changed after creation

### Home Assistant Add-on Constraints

- Configuration options are limited to basic types (string, int, bool)
- Complex validation must be handled in the container startup script
- Configuration changes require add-on restart

### Docker Image Considerations

- Alpha/beta images should use the same base image as production
- Image tags must be unique to prevent conflicts
- Registry storage costs increase with more image variants