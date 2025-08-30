# Boomberman Alpha Add-on Documentation

## ⚠️ IMPORTANT: Alpha Version Warning

**This is an ALPHA version of the Boomberman add-on intended for development and testing purposes only.**

- ❌ **NOT recommended for production use**
- ❌ **May contain bugs, incomplete features, or breaking changes**
- ❌ **No stability guarantees**
- ❌ **Features may be removed or changed without notice**
- ✅ **Frequent updates with latest experimental features**
- ✅ **Ideal for developers and advanced testers**

## Version Differences

### Alpha vs Beta vs Production

| Feature                  | Alpha        | Beta              | Production |
| ------------------------ | ------------ | ----------------- | ---------- |
| **Stability**            | Experimental | Release Candidate | Stable     |
| **Update Frequency**     | Very High    | Medium            | Low        |
| **Bug Risk**             | High         | Medium            | Low        |
| **Feature Completeness** | Partial      | Near Complete     | Complete   |
| **Production Ready**     | No           | Caution           | Yes        |
| **Support Level**        | Community    | Limited           | Full       |

### What's Different in Alpha

- **Latest Development Features**: Access to cutting-edge bot detection algorithms and security enhancements
- **Experimental Configuration Options**: New settings that may change or be removed
- **Enhanced Logging**: Detailed debug information for development purposes
- **Rapid Iteration**: Features are added and modified frequently based on development progress

## Installation Instructions

### Prerequisites

1. Home Assistant OS or Supervised installation
2. Add-on store access
3. **Understanding that this is unstable software**

### Installation Steps

1. **Add Repository** (if not already added):
   - Go to **Settings** → **Add-ons** → **Add-on Store**
   - Click the **⋮** menu → **Repositories**
   - Add: `https://github.com/BelphegorPrime/ha-addon-collection`

2. **Install Alpha Version**:
   - Browse to **Boomberman Alpha** in the add-on store
   - Click **Install** (this may take several minutes)
   - ⚠️ **Read all warnings before proceeding**

3. **Configuration**:
   - Configure the add-on through the **Configuration** tab
   - Alpha versions may have additional experimental options
   - Some options may not be fully documented yet

4. **Start the Add-on**:
   - Go to the **Info** tab
   - Click **Start**
   - Monitor logs for any issues

### Configuration Options

The alpha version includes all standard Boomberman configuration options plus experimental features:

#### Standard Options
- **AI Enabled**: Enable/disable AI-powered bot detection
- **Ollama URL**: URL for Ollama AI service
- **Ollama model**: AI model to use for detection

#### Alpha-Specific Options
- **Bot Detection Enabled**: Enable enhanced bot detection (experimental)
- **Bot Detection Threshold Suspicious**: Threshold for suspicious activity (0-100)
- **Bot Detection Threshold High Risk**: Threshold for high-risk activity (0-100)
- **Log Retention Days**: How long to keep logs (1-365 days)
- **High Risk Countries**: Comma-separated country codes for geographic analysis
- **VPN Penalty Score**: Additional penalty for VPN traffic (0-100)
- **Hosting Provider Penalty**: Additional penalty for hosting providers (0-100)
- **Whitelist IPs**: Comma-separated list of trusted IP addresses
- **Whitelist ASNs**: Comma-separated list of trusted ASN numbers

## Troubleshooting

### Common Alpha Issues

1. **Add-on Won't Start**:
   - Check logs for configuration errors
   - Verify all required options are set
   - Some experimental features may conflict

2. **Unexpected Behavior**:
   - This is expected in alpha versions
   - Report issues to the development team
   - Consider switching to beta or production version

3. **Configuration Changes Not Applied**:
   - Restart the add-on after configuration changes
   - Some alpha features may require container restart

### Getting Help

- **GitHub Issues**: Report bugs and feature requests
- **Community Forum**: General discussion and community support
- **Development Chat**: Real-time discussion with developers (if available)

## Migration Path

### Upgrading from Alpha

When ready to move to a more stable version:

1. **To Beta**: Automatic upgrade path when beta releases are available
2. **To Production**: Manual migration may be required for some settings
3. **Configuration Backup**: Export your configuration before switching versions

### Downgrading from Alpha

If you need to move to a stable version:

1. Stop the alpha add-on
2. Install the production version
3. Migrate compatible configuration settings
4. Some alpha-specific settings will be lost

## Development Information

### Release Schedule

- **Alpha Releases**: Triggered by development branch pushes
- **Update Frequency**: Multiple times per week during active development
- **Version Format**: `alpha-{branch-name}-{timestamp}`

### Feedback and Contributions

Your feedback helps improve Boomberman:

- Test new features and report issues
- Provide feedback on experimental configurations
- Contribute to documentation improvements
- Share use cases and feature requests

## Disclaimer

**Use at your own risk.** The alpha version is provided as-is for testing and development purposes. The developers are not responsible for any issues, data loss, or security problems that may arise from using alpha software in production environments.

For production use, please use the stable **Boomberman** add-on instead.