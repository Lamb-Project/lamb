# LAMB Updated Playwright Tests

Updated Playwright test suite created using MCP (Model Context Protocol) tools for comprehensive testing of LAMB application functionality.

## Overview

These tests were created by exploring the actual LAMB application using MCP Playwright tools to understand the current UI structure and create reliable automated tests. Unlike the original tests that were failing due to outdated UI selectors, these tests are based on the actual application state.

## Test Files

### `organization_llm_test.js`
**Focus:** Organization management and LLM configuration
- ✅ Create organizations with signup keys
- ✅ Configure LLM providers (enable/disable)
- ✅ Create users within organizations
- ✅ Verify organization isolation
- ✅ Test organization-specific LLM access

**Key Features Tested:**
- Organization CRUD operations
- LLM provider configuration (OpenAI, Anthropic, Ollama)
- User creation and role assignment
- Organization-scoped settings
- LLM availability based on organization config

### `mcp_comprehensive_test.js`
**Focus:** End-to-end workflow testing
- Organization creation and configuration
- User management
- Knowledge base creation and document upload
- Assistant creation with KB integration
- Chat functionality testing
- End user signup flows

**Note:** This is a more complex test that may need adjustments based on current UI state.

## Prerequisites

### Services Running
```bash
# Start all services
docker-compose up -d

# Verify services are accessible
curl http://localhost:5173    # Frontend
curl http://localhost:9099/status  # Backend
curl http://localhost:8080    # OpenWebUI
curl http://localhost:9090/api/status  # KB Server
```

### Dependencies
```bash
cd testing/playwright_updated
npm install
```

### Admin Access
Tests assume admin user is logged in with credentials:
- Email: `admin@owi.com`
- Password: `admin`

## Running Tests

### Run All Tests
```bash
cd testing/playwright_updated
./run_tests.sh
```

### Run Individual Tests
```bash
# Organization & LLM Configuration Test
node organization_llm_test.js http://localhost:5173

# Comprehensive Test (Advanced)
node mcp_comprehensive_test.js http://localhost:5173
```

### Debug Mode
```bash
# Run with visible browser for debugging
node organization_llm_test.js http://localhost:5173
# Tests run with headless: false by default
```

## Test Data Created

Tests create real data in the LAMB system:

### Organizations
- `Test Org {timestamp}` - Organizations with unique names
- Signup keys for user registration
- Custom LLM configurations

### Users
- Organization-specific users
- Creator and end-user types
- Unique email addresses with timestamps

### Assistants & Knowledge Bases
- Test assistants with KB integration
- Sample documents for testing
- RAG-enabled configurations

## Test Results Verification

After running tests, verify in the admin panel:

1. **Organizations Tab:** Check for newly created organizations
2. **User Management:** Verify created users and their roles
3. **Assistant List:** Check for test assistants
4. **Knowledge Bases:** Verify uploaded documents

## Test Architecture

### MCP-Based Creation
- Tests created by exploring actual application UI
- Uses real selectors and element structures
- Accounts for dynamic content and loading states
- Includes proper wait strategies

### Error Handling
- Graceful degradation for optional features
- Detailed logging of test progress
- Clear success/failure indicators
- Test data cleanup considerations

### Organization Isolation
- Tests verify proper data separation
- LLM availability based on org configuration
- User access control validation
- Multi-tenant functionality confirmation

## Troubleshooting

### Common Issues

**"Element not found" errors:**
- UI may have changed since test creation
- Run with `headless: false` to debug visually
- Check browser console for JavaScript errors

**Authentication failures:**
- Ensure admin user is logged in
- Check backend environment variables
- Verify database connectivity

**Service unavailable:**
- Confirm all containers are running
- Check Docker logs: `docker-compose logs`
- Verify network connectivity

### Debug Tips
```bash
# Run with maximum visibility
DEBUG=pw:api node organization_llm_test.js http://localhost:5173

# Check browser console logs
# Tests include console.log statements for progress tracking
```

## Extending Tests

### Adding New Test Cases
1. Use MCP tools to explore new UI areas
2. Identify stable selectors and interaction patterns
3. Add proper wait strategies
4. Include cleanup for test data

### Test Data Management
- Use timestamps for unique identifiers
- Consider cleanup functions for test data
- Document created resources for manual verification

## Integration with CI/CD

Tests can be integrated into CI pipelines:

```yaml
# Example GitHub Actions
- name: Run LAMB Tests
  run: |
    cd testing/playwright_updated
    npm install
    ./run_tests.sh
```

## Maintenance

### Regular Updates Needed
- UI changes may break selectors
- New features require additional tests
- API changes affect backend interactions
- Dependency updates may require test adjustments

### Best Practices
- Run tests regularly against development environment
- Update tests when UI changes are made
- Document any manual test steps that can't be automated
- Keep test data realistic but isolated

## Related Documentation

- [LAMB Architecture](../../Documentation/lamb_architecture.md)
- [Original Playwright Tests](../playwright/README.md)
- [Test Markdown Scripts](../markdown_scripts/)
- [MCP Playwright Tools](../../.cursor/mcp/playwright/)
