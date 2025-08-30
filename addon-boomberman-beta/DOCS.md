# Boomberman Beta Add-on Documentation

## ⚠️ IMPORTANT: Beta Version Notice

**This is a BETA version of the Boomberman add-on intended for pre-release testing and early access to new features.**

- ⚠️ **Use with caution in production environments**
- ⚠️ **May contain minor bugs or incomplete features**
- ⚠️ **Features are near-complete but not fully validated**
- ✅ **More stable than alpha versions**
- ✅ **Access to upcoming features before general release**
- ✅ **Suitable for advanced users and testers**

## Version Differences

### Beta vs Alpha vs Production

| Feature                  | Alpha        | Beta              | Production |
| ------------------------ | ------------ | ----------------- | ---------- |
| **Stability**            | Experimental | Release Candidate | Stable     |
| **Update Frequency**     | Very High    | Medium            | Low        |
| **Bug Risk**             | High         | Medium            | Low        |
| **Feature Completeness** | Partial      | Near Complete     | Complete   |
| **Production Ready**     | No           | Caution           | Yes        |
| **Support Level**        | Community    | Limited           | Full       |
| **Testing Level**        | Minimal      | Extensive         | Complete   |

### What's Different in Beta

- **Release Candidate Features**: Features planned for the next stable release
- **Enhanced Bot Detection**: Improved algorithms with better accuracy
- **Advanced Configuration**: More granular control over security settings
- **Stability Focus**: Fewer experimental changes, more focus on reliability
- **Pre-release Testing**: Extensive testing before promotion to production

## Installation Instructions

### Prerequisites

1. Home Assistant OS or Supervised installation
2. Add-on store access
3. **Willingness to test pre-release software**
4. **Basic troubleshooting knowledge recommended**

### Installation Steps

1. **Add Repository** (if not already added):
   - Go to **Settings** → **Add-ons** → **Add-on Store**
   - Click the **⋮** menu → **Repositories**
   - Add: `https://github.com/BelphegorPrime/ha-addon-collection`

2. **Install Beta Version**:
   - Browse to **Boomberman Beta** in the add-on store
   - Click **Install** (this may take several minutes)
   - ⚠️ **Review beta warnings before proceeding**

3. **Configuration**:
   - Configure the add-on through the **Configuration** tab
   - Beta versions include new features not yet in production
   - All options should be documented and stable

4. **Start the Add-on**:
   - Go to the **Info** tab
   - Click **Start**
   - Monitor logs during initial startup

### Configuration Options

The beta version includes all production configuration options plus new features being prepared for release:

#### Standard Options
- **AI Enabled**: Enable/disable AI-powered bot detection
- **Ollama URL**: URL for Ollama AI service
- **Ollama model**: AI model to use for detection

#### Beta Features (Upcoming in Production)
- **Bot Detection Enabled**: Enable enhanced bot detection system
- **Bot Detection Threshold Suspicious**: Threshold for marking activity as suspicious (0-100)
- **Bot Detection Threshold High Risk**: Threshold for high-risk activity blocking (0-100)
- **Log Retention Days**: Number of days to retain log files (1-365)
- **High Risk Countries**: Comma-separated ISO country codes for geographic analysis
- **VPN Penalty Score**: Additional risk score for VPN traffic (0-100)
- **Hosting Provider Penalty**: Additional risk score for hosting provider IPs (0-100)
- **Whitelist IPs**: Comma-separated list of always-trusted IP addresses
- **Whitelist ASNs**: Comma-separated list of trusted Autonomous System Numbers

#### Configuration Validation

Beta versions include enhanced validation:
- Threshold values must be between 0-100
- Country codes must be valid ISO 3166-1 alpha-2 codes
- IP addresses must be valid IPv4 or IPv6 format
- ASN numbers must be valid integers

## Troubleshooting

### Common Beta Issues

1. **Configuration Validation Errors**:
   - Check that all values are within specified ranges
   - Verify country codes are valid (e.g., "US", "GB", "DE")
   - Ensure IP addresses are properly formatted

2. **Performance Issues**:
   - Enhanced bot detection may increase CPU usage
   - Adjust thresholds if experiencing high load
   - Monitor system resources during peak traffic

3. **False Positives**:
   - Fine-tune detection thresholds
   - Add legitimate IPs to whitelist
   - Review geographic penalty settings

### Getting Help

- **GitHub Issues**: Report bugs with detailed logs
- **Community Forum**: Discussion and user support
- **Documentation**: Check for updated configuration guides
- **Migration Support**: Help moving between versions

## Migration and Compatibility

### Upgrading to Beta

From Production:
1. Stop the production add-on
2. Install beta version
3. Copy compatible configuration settings
4. Configure new beta-specific options
5. Test thoroughly before relying on it

From Alpha:
1. Beta versions are more stable than alpha
2. Most alpha configurations should be compatible
3. Some experimental alpha features may not be available

### Downgrading from Beta

To Production:
1. Export your current configuration
2. Install production version
3. Import compatible settings (beta-specific options will be ignored)
4. Verify functionality

## Testing and Feedback

### What to Test

- **New Configuration Options**: Try different threshold combinations
- **Bot Detection Accuracy**: Monitor false positives and negatives
- **Performance Impact**: Check system resource usage
- **Geographic Filtering**: Test with various country configurations
- **Whitelist Functionality**: Verify trusted IPs are not blocked

### Providing Feedback

Your testing helps improve the final release:

1. **Bug Reports**: Include logs, configuration, and steps to reproduce
2. **Feature Feedback**: Share your experience with new options
3. **Performance Data**: Report any resource usage concerns
4. **Use Case Scenarios**: Describe how you're using the beta features

## Release Information

### Beta Release Schedule

- **Beta Releases**: Created from release candidate branches
- **Update Frequency**: Weekly to bi-weekly during release cycles
- **Version Format**: `beta-{branch-name}-{timestamp}`
- **Promotion Path**: Successful betas become production releases

### Feature Stability

Beta features are:
- ✅ **Functionally complete**
- ✅ **Tested in development environments**
- ✅ **Documented with known limitations**
- ⚠️ **May have minor bugs or edge cases**
- ⚠️ **Subject to final adjustments before production**

## Production Readiness

### When to Use Beta

- You want early access to new features
- You can tolerate minor issues
- You want to provide feedback on upcoming releases
- You have the ability to troubleshoot problems
- You can switch back to production if needed

### When to Use Production Instead

- You need maximum stability
- You're running critical security infrastructure
- You prefer well-tested, proven features
- You don't want to deal with potential issues
- You need guaranteed long-term support

## Disclaimer

Beta software is more stable than alpha but still carries risks. While suitable for advanced users and testing environments, use caution in production. The developers provide limited support for beta versions and recommend thorough testing before deployment in critical environments.

For maximum stability and full support, use the production **Boomberman** add-on.