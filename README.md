# ha-addon-collection

# Home Assistant add-on collection repository

Add-on documentation: <https://developers.home-assistant.io/docs/add-ons>

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FBelphegorPrime%2Fha-addon-collection)

## Add-ons

This repository contains the following add-ons

### Authelia add-on

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armv7 Architecture][armv7-shield]

### Boomberman add-on

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armv7 Architecture][armv7-shield]

## Boomberman Add-on Versions

This repository provides three versions of the Boomberman add-on to meet different user needs:

### 🟢 Boomberman (Production/Stable)
- **Recommended for production use**
- Latest stable release with full testing and validation
- Updated only with stable releases
- Most reliable version for everyday use
- Full feature set with proven stability

### 🟡 Boomberman Beta (Release Candidate)
- **For advanced users wanting early access**
- Pre-release version for final testing before stable release
- Contains features planned for the next stable release
- More stable than alpha but may contain minor issues
- Recommended for users who want to test upcoming features

### 🔴 Boomberman Alpha (Development)
- **For testing and development purposes only**
- Development builds with the latest experimental features
- Frequent updates from active development branches
- May contain bugs, incomplete features, or breaking changes
- Only recommended for developers and testers

### Installation Instructions

1. Add this repository to your Home Assistant add-on store using the button above
2. Browse the available add-ons and choose the appropriate Boomberman version:
   - **Production**: For stable, everyday use
   - **Beta**: For early access to upcoming features (some risk)
   - **Alpha**: For testing latest developments (high risk)

### Architecture Support

All Boomberman versions support the same architectures:
- **aarch64** (ARM 64-bit) - Raspberry Pi 4, etc.
- **amd64** (x86 64-bit) - Intel/AMD processors
- **armv7** (ARM 32-bit) - Raspberry Pi 3, etc.

### Version Selection Guide

| Use Case             | Recommended Version | Risk Level |
| -------------------- | ------------------- | ---------- |
| Home production use  | **Production**      | Low        |
| Testing new features | **Beta**            | Medium     |
| Development/Testing  | **Alpha**           | High       |
| First-time users     | **Production**      | Low        |

<!--

Notes to developers after forking or using the github template feature:
- While developing comment out the 'image' key from 'example/config.yaml' to make the supervisor build the addon
  - Remember to put this back when pushing up your changes.
- When you merge to the 'main' branch of your repository a new build will be triggered.
  - Make sure you adjust the 'version' key in 'example/config.yaml' when you do that.
  - Make sure you update 'example/CHANGELOG.md' when you do that.
  - The first time this runs you might need to adjust the image configuration on github container registry to make it public
  - You may also need to adjust the github Actions configuration (Settings > Actions > General > Workflow > Read & Write)
- Adjust the 'image' key in 'example/config.yaml' so it points to your username instead of 'home-assistant'.
  - This is where the build images will be published to.
- Rename the example directory.
  - The 'slug' key in 'example/config.yaml' should match the directory name.
- Adjust all keys/url's that points to 'home-assistant' to now point to your user/fork.
- Share your repository on the forums https://community.home-assistant.io/c/projects/9
- Do awesome stuff!
 -->

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
