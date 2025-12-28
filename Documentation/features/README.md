# Feature Documentation

This directory contains detailed documentation for specific LAMB features. Each document provides implementation details, API specifications, and usage patterns that go beyond the overview in [lamb_architecture_v2.md](../lamb_architecture_v2.md).

## Available Feature Docs

| Feature | Document | Status |
|---------|----------|--------|
| Assistant Sharing | [assistant_sharing.md](./assistant_sharing.md) | ✅ Complete |
| Knowledge Base Sharing | [kb_sharing.md](./kb_sharing.md) | 📝 Planned |
| LTI Integration | [lti_integration.md](./lti_integration.md) | 📝 Planned |
| Chat Analytics | [../chat_analytics_project.md](../chat_analytics_project.md) | ✅ Complete |
| User Blocking | [user_blocking.md](./user_blocking.md) | 📝 Planned |
| Multimodal Support | [multimodal.md](./multimodal.md) | 📝 Planned |
| Image Generation | [image_generation.md](./image_generation.md) | 📝 Planned |

## Document Template

Each feature document should follow this structure:

```markdown
# Feature Name

## Overview
Brief description of the feature and its purpose.

## Architecture
How the feature fits into the system.

## Database Schema
Tables and fields specific to this feature.

## API Endpoints
Complete endpoint documentation with examples.

## Frontend Integration
UI components and patterns.

## Configuration
Required configuration options.

## Usage Examples
Common use cases with code examples.

## Security Considerations
Access control and security notes.

## Troubleshooting
Common issues and solutions.
```

## When to Create a Feature Doc

Create a dedicated feature document when:
- Feature has multiple API endpoints
- Feature requires detailed configuration
- Feature has complex frontend integration
- Feature is commonly extended or customized
- Feature documentation exceeds ~50 lines in main architecture doc

## Contributing

When adding a new feature doc:
1. Use the template structure above
2. Update this README with the new document
3. Add a brief mention in `lamb_architecture_v2.md` with link
4. Update `DOCUMENTATION_INDEX.md` if needed

