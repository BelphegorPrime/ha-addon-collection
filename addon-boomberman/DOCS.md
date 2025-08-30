# Boomberman Add-on Documentation

## Overview

**Boomberman** is a production-ready Home Assistant add-on that provides advanced bot detection and security features to protect your Home Assistant instance from malicious traffic and automated attacks.

✅ **Production Ready**: Fully tested and validated for everyday use  
✅ **Stable**: Reliable performance with proven features  
✅ **Supported**: Full documentation and community support  
✅ **Secure**: Battle-tested security features  

## Version Information

This is the **production/stable** version of Boomberman. For users who want to test upcoming features, alpha and beta versions are also available:

| Version                       | Stability         | Use Case            | Update Frequency |
| ----------------------------- | ----------------- | ------------------- | ---------------- |
| **Production** (this version) | Stable            | Everyday use        | Monthly          |
| **Beta**                      | Release Candidate | Early access        | Bi-weekly        |
| **Alpha**                     | Experimental      | Development/Testing | Daily            |

## Features

### Core Security Features
- **AI-Powered Bot Detection**: Advanced machine learning algorithms to identify malicious bots
- **Real-time Traffic Analysis**: Monitor and analyze incoming requests
- **Automatic Blocking**: Block suspicious IPs and patterns automatically
- **Customizable Rules**: Configure detection sensitivity and blocking behavior

### Integration Features
- **Home Assistant Integration**: Seamless integration with Home Assistant ecosystem
- **Ollama AI Support**: Leverage local AI models for enhanced detection
- **Logging and Monitoring**: Comprehensive logs for security analysis
- **Dashboard Integration**: View security metrics in Home Assistant

## Installation Instructions

### Prerequisites

1. **Home Assistant OS** or **Home Assistant Supervised**
2. **Add-on Store Access**: Supervisor privileges required
3. **System Resources**: Minimum 1GB RAM recommended
4. **Network Access**: Internet connection for initial setup

### Installation Steps

1. **Add Repository**:
   - Navigate to **Settings** → **Add-ons** → **Add-on Store**
   - Click the **⋮** menu in the top-right corner
   - Select **Repositories**
   - Add repository URL: `https://github.com/BelphegorPrime/ha-addon-collection`
   - Click **Add**

2. **Install Boomberman**:
   - Refresh the add-on store
   - Find **Boomberman** in the available add-ons
   - Click **Install**
   - Wait for installation to complete (may take several minutes)

3. **Initial Configuration**:
   - Go to the **Configuration** tab
   - Configure basic settings (see Configuration section below)
   - Click **Save**

4. **Start the Add-on**:
   - Navigate to the **Info** tab
   - Click **Start**
   - Monitor the **Log** tab for successful startup

## Configuration

### Basic Configuration

#### AI Settings
- **AI Enabled**: `true/false`
  - Enable AI-powered bot detection
  - Default: `false`
  - Requires Ollama configuration if enabled

- **Ollama URL**: `string`
  - URL to your Ollama AI service
  - Format: `http://your-ollama-host:11434`
  - Required if AI Enabled is true

- **Ollama model**: `string`
  - AI model to use for detection
  - Default: `llama3.2`
  - Must be available on your Ollama instance

### Example Configuration

```yaml
AI Enabled: true
Ollama URL: "http://192.168.1.100:11434"
Ollama model: "llama3.2"
```

### Advanced Configuration

For advanced users, additional configuration options may be available through the Home Assistant configuration files. Consult the advanced configuration guide for details.

## Usage

### Getting Started

1. **Install and Start**: Follow installation instructions above
2. **Monitor Logs**: Check the Log tab for activity and any issues
3. **Review Security**: Monitor Home Assistant logs for blocked requests
4. **Adjust Settings**: Fine-tune configuration based on your needs

### Monitoring Security

- **Add-on Logs**: View real-time detection activity
- **Home Assistant Logs**: See blocked requests and security events
- **System Performance**: Monitor resource usage in Home Assistant

### Best Practices

1. **Regular Updates**: Keep the add-on updated to the latest version
2. **Log Monitoring**: Regularly review logs for security events
3. **Configuration Backup**: Backup your configuration settings
4. **Performance Monitoring**: Watch system resources during high traffic

## Troubleshooting

### Common Issues

#### Add-on Won't Start
**Symptoms**: Add-on fails to start or crashes immediately

**Solutions**:
1. Check configuration syntax in the Configuration tab
2. Verify Ollama URL is accessible (if AI enabled)
3. Ensure sufficient system resources
4. Review logs for specific error messages

#### AI Detection Not Working
**Symptoms**: Bot detection seems ineffective

**Solutions**:
1. Verify Ollama service is running and accessible
2. Check that the specified model is available
3. Confirm AI Enabled is set to true
4. Review Ollama logs for connection issues

#### High Resource Usage
**Symptoms**: System performance degradation

**Solutions**:
1. Consider disabling AI features if not needed
2. Adjust detection sensitivity
3. Monitor during peak traffic periods
4. Upgrade system resources if necessary

### Getting Help

- **Community Forum**: [Home Assistant Community](https://community.home-assistant.io/)
- **GitHub Issues**: Report bugs and feature requests
- **Documentation**: Check for updated guides and tutorials
- **Discord/Chat**: Real-time community support (if available)

## Maintenance

### Regular Maintenance Tasks

1. **Update Add-on**: Check for updates monthly
2. **Review Logs**: Weekly log review for security events
3. **Configuration Review**: Quarterly settings review
4. **Performance Check**: Monitor resource usage trends

### Backup and Recovery

1. **Configuration Backup**: Export add-on configuration regularly
2. **Home Assistant Backup**: Include add-on in system backups
3. **Recovery Testing**: Periodically test backup restoration

## Migration

### Upgrading from Beta/Alpha

If you're currently using a beta or alpha version:

1. **Export Configuration**: Save your current settings
2. **Stop Beta/Alpha**: Stop the pre-release version
3. **Install Production**: Install this stable version
4. **Import Settings**: Configure with your saved settings
5. **Test Functionality**: Verify everything works as expected

### Downgrading (Not Recommended)

Downgrading from production to beta/alpha is not recommended but possible:

1. **Backup Current Config**: Save your working configuration
2. **Understand Risks**: Beta/alpha versions may be unstable
3. **Install Target Version**: Install the desired version
4. **Reconfigure**: Some settings may not be compatible

## Architecture Support

Boomberman supports all major Home Assistant architectures:

- **amd64**: Intel/AMD 64-bit processors
- **aarch64**: ARM 64-bit (Raspberry Pi 4, etc.)
- **armv7**: ARM 32-bit (Raspberry Pi 3, etc.)

## Security Considerations

### Network Security
- Boomberman analyzes incoming traffic patterns
- Blocked IPs are logged for security auditing
- Consider firewall rules for additional protection

### Privacy
- All processing happens locally on your Home Assistant instance
- No data is sent to external services (except configured AI services)
- Logs contain IP addresses and request patterns

### Performance Impact
- Minimal impact on normal Home Assistant operations
- AI features may increase CPU usage
- Monitor system resources during initial deployment

## Support and Community

### Official Support
- **Documentation**: Comprehensive guides and tutorials
- **GitHub**: Bug reports and feature requests
- **Community Forum**: User discussions and support

### Community Resources
- **User Guides**: Community-created tutorials
- **Configuration Examples**: Shared configurations
- **Troubleshooting Tips**: Community solutions

## Changelog

For detailed information about updates and changes, see the CHANGELOG.md file in the add-on directory.

## License

This add-on is released under the MIT License. See LICENSE file for details.

---

**Need help?** Check the troubleshooting section above or reach out to the community for support. For the most stable experience, always use this production version unless you specifically need features from beta or alpha releases.