# Home Assistant Add-on: Boomberman Beta

## About

This is the **Beta version** of the Boomberman add-on. Beta versions are release candidates that contain the latest stable features and have undergone more testing than alpha versions, but may still contain minor issues.

⚠️ **Warning**: This is a pre-release version intended for final testing before production release. While more stable than alpha versions, use with caution in production environments.

## Installation

1. Navigate to the Home Assistant Add-on Store
2. Add this repository if you haven't already
3. Find "Boomberman Beta" in the add-on list
4. Click "Install"
5. Configure the add-on options as needed
6. Start the add-on

## Configuration

The beta version includes all the latest stable configuration options:

### Basic Options
- **AI Enabled**: Enable or disable AI features
- **Ollama URL**: URL to your Ollama instance
- **Ollama model**: AI model to use

### Bot Detection (Enhanced)
- **Bot Detection Enabled**: Enable enhanced bot detection
- **Bot Detection Threshold Suspicious**: Threshold for suspicious activity (0-100)
- **Bot Detection Threshold High Risk**: Threshold for high-risk activity (0-100)
- **High Risk Countries**: Comma-separated list of country codes
- **VPN Penalty Score**: Penalty score for VPN usage (0-100)
- **Hosting Provider Penalty**: Penalty for hosting provider IPs (0-100)

### System Configuration
- **Log Retention Days**: Number of days to retain logs (1-365)
- **Whitelist IPs**: Comma-separated list of whitelisted IP addresses
- **Whitelist ASNs**: Comma-separated list of whitelisted ASN numbers

## Differences from Stable Version

The beta version includes:
- Latest tested features and improvements
- Bug fixes that will be included in the next stable release
- Performance optimizations
- Updated dependencies that have passed testing

## Differences from Alpha Version

Beta versions are more stable than alpha versions:
- Features have undergone additional testing
- Known critical bugs have been fixed
- Performance has been validated
- Configuration options are finalized

## Support

For issues with the beta version, please report them in the main repository with the "beta" label. Beta issues are prioritized for the next stable release.

## Version Information

This beta version represents a release candidate for the next stable version. It receives updates less frequently than alpha but more frequently than stable releases.