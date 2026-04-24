# Tenant System Verification Checklist

Use this checklist to verify that the tenant-aware configuration system is working correctly.

## Phase 1: Pre-Integration Testing (5 minutes)

### ✅ Check Files Exist

```bash
cd Website
ls -la tenant_resolver.py
ls -la tenant_config.py
ls -la tenant_guards.py
ls -la tenant_templates.py
ls -la tenants.json
ls -la test_tenant_system.py
ls -la templates/error_403.html
```

**Expected:** All files should exist and be readable

### ✅ Check Syntax

```bash
python -m py_compile tenant_resolver.py
python -m py_compile tenant_config.py
python -m py_compile tenant_guards.py
python -m py_compile tenant_templates.py
```

**Expected:** No errors

### ✅ Run Unit Tests

```bash
pip install pytest  # If not already installed
pytest test_tenant_system.py -v
```

**Expected Output:**
```
test_tenant_system.py::TestTenantResolver::test_extract_subdomain_valid PASSED
test_tenant_system.py::TestTenantResolver::test_extract_subdomain_with_port PASSED
...
====== 30+ passed in 0.5s ======
```

### ✅ Verify Configuration Loading

```python
python -c "
from tenant_config import get_config_manager
import json

manager = get_config_manager()
print('Configuration loaded successfully!')
print(json.dumps(manager._config, indent=2))
"
```

**Expected:** Configuration is printed without errors

---

## Phase 2: Flask Integration Testing (10 minutes)

### ✅ Check main.py Integration

```bash
grep -n "import tenant_" main.py
```

**Expected Output:**
```
27: import tenant_resolver
28: import tenant_config
29: import tenant_guards
30: import tenant_templates
```

### ✅ Verify Middleware is Registered

```bash
grep -n "resolve_tenant_context\|inject_tenant_context" main.py
```

**Expected Output:**
```
39: app.context_processor(tenant_templates.inject_tenant_context)
43: def resolve_tenant_context():
```

### ✅ Check Error Handler

```bash
grep -n "@app.errorhandler(403)" main.py
```

**Expected:** Should find the error handler registered

### ✅ Test Flask App Starts

```bash
# In one terminal
python main.py

# Wait for startup...
# Look for: Running on http://0.0.0.0:4999
```

**Expected:** App starts without errors

If there are import errors, check:
1. All tenant*.py files are in the Website directory
2. Python path is correct
3. Dependencies are installed (Flask, etc.)

---

## Phase 3: Manual Testing (15 minutes)

Keep Flask running and test in another terminal.

### ✅ Test 1: Default Tenant Access

```bash
# Test a public page (should work)
curl -I http://localhost:4999/
# Expected: 200 OK or 302 redirect

# Test a disabled module (should fail with 403)
curl -I http://localhost:4999/chat
# Expected: 403 Forbidden (for default tenant with chat disabled)
```

### ✅ Test 2: Tenant Resolution with Header

```bash
# Test with school1 tenant (chat should be enabled)
curl -H "X-Tenant-ID: school1" -I http://localhost:4999/chat
# Expected: 200 OK or redirect (module is enabled for school1)

# Test with school2 tenant (chat should be disabled)
curl -H "X-Tenant-ID: school2" -I http://localhost:4999/chat
# Expected: 403 Forbidden (module is disabled for school2)
```

### ✅ Test 3: JSON Error Response

```bash
# Request JSON response for disabled module
curl -H "Accept: application/json" \
     http://localhost:4999/chat
# Expected response:
# {
#   "error": "Module not available",
#   "message": "The chat module is not available for your organization.",
#   "module": "chat"
# }
```

### ✅ Test 4: 403 Error Page

```bash
# Open in browser and see error page
curl http://localhost:4999/chat | head -20
# Should contain HTML with "403" and "Zugriff verweigert"
```

### ✅ Test 5: Check Template Context

Add temporary debug route to main.py:

```python
@app.route('/debug/config')
def debug_config():
    from tenant_config import get_enabled_modules
    enabled = get_enabled_modules(g.tenant_id)
    return {
        'tenant': g.tenant_id,
        'enabled_modules': list(enabled)
    }
```

Test it:
```bash
curl http://localhost:4999/debug/config
# Should show JSON with tenant and modules
```

---

## Phase 4: Configuration Testing (5 minutes)

### ✅ Test Different Tenant Configs

```bash
# Check what's enabled for default
curl -H "X-Tenant-ID: default" http://localhost:4999/debug/config | python -m json.tool

# Check what's enabled for school1
curl -H "X-Tenant-ID: school1" http://localhost:4999/debug/config | python -m json.tool

# Check what's enabled for partner-org
curl -H "X-Tenant-ID: partner-org" http://localhost:4999/debug/config | python -m json.tool
```

**Expected:** Each tenant shows different enabled modules matching tenants.json

### ✅ Test Config Reload

```python
from tenant_config import get_config_manager

manager = get_config_manager()
print(manager.is_module_enabled('school1', 'chat'))

# Reload configuration
manager.reload()
print(manager.is_module_enabled('school1', 'chat'))
```

**Expected:** Should print True (twice) or False (twice) without errors

---

## Phase 5: Post-Decorator Testing (30 minutes)

After you've added decorators to routes:

### ✅ Verify Decorators Added

```bash
grep -c "@tenant_guards.require" main.py
# Should be >= 25
```

### ✅ Test Protected Routes

For each protected route, test both allowed and denied access:

```bash
# Blog - should be enabled for default
curl -I http://localhost:4999/blog
# Expected: 200 or redirect (allowed)

# Tickets - should be disabled for default
curl -I http://localhost:4999/tickets
# Expected: 403 (denied)

# Admin - should be disabled for default
curl -I http://localhost:4999/admin/dashboard
# Expected: 403 (denied)
```

### ✅ Test Admin Routes

```bash
# Admin should be disabled for default
curl -I http://localhost:4999/admin/users
# Expected: 403

# Admin should be enabled for school1
curl -H "X-Tenant-ID: school1" -I http://localhost:4999/admin/users
# Expected: 200 or redirect to login (module exists, just needs auth)
```

### ✅ Test Feature Combinations

Test that combining decorators works:

```bash
# Admin + module check
curl -I http://localhost:4999/admin/invoices
# Expected: 403 (admin disabled for default)

curl -H "X-Tenant-ID: school1" -I http://localhost:4999/admin/invoices
# Expected: 200 or redirect (both admin and invoices enabled for school1)
```

---

## Phase 6: Template Testing (10 minutes)

### ✅ Check Template Functions Available

Create a test template:

```jinja2
<!-- test_tenant.html -->
Current Tenant: {{ tenant_id }}
Chat Enabled: {{ module_enabled('chat') }}
Blog Enabled: {{ module_enabled('blog') }}

Enabled Modules:
{% for module in enabled_modules %}
  - {{ module }}
{% endfor %}
```

Add test route:

```python
@app.route('/test/tenant')
def test_tenant():
    return render_template('test_tenant.html')
```

Test it:

```bash
curl http://localhost:4999/test/tenant
# Should show: Current Tenant: default, Chat Enabled: True, etc.

curl -H "X-Tenant-ID: school1" http://localhost:4999/test/tenant
# Should show: Current Tenant: school1, Chat Enabled: False, etc.
```

---

## Phase 7: Edge Case Testing (10 minutes)

### ✅ Invalid Tenant ID

```bash
curl -H "X-Tenant-ID: invalid@tenant#id" http://localhost:4999/debug/config
# Should fall back to default tenant
```

### ✅ Missing Module Config

Add a new module to a route but not to tenants.json:

```python
@app.route('/test/new-module')
@tenant_guards.require_module('nonexistent')
def test_new():
    return "OK"
```

Test:

```bash
curl -I http://localhost:4999/test/new-module
# Expected: 403 (module not configured, defaults to disabled)
```

### ✅ Malformed JSON Response

```bash
curl -H "Accept: application/json" \
     http://localhost:4999/test/new-module
# Should return valid JSON with error
```

---

## Testing Summary

### Quick Test Script

```bash
#!/bin/bash

echo "Testing tenant system..."
echo

# Test 1: Configuration
echo "✓ Testing configuration loading..."
python -c "from tenant_config import get_config_manager; get_config_manager()" || exit 1

# Test 2: Unit tests
echo "✓ Running unit tests..."
pytest test_tenant_system.py -q || exit 1

# Test 3: Flask startup
echo "✓ Testing Flask app..."
python -c "import main" || exit 1

echo
echo "✅ All tests passed!"
```

Save as `test_tenant.sh`, run with `bash test_tenant.sh`

---

## Troubleshooting

### Issue: Import errors

**Fix:**
```bash
# Check Python path
python -c "import sys; print(sys.path)"

# Ensure you're in Website directory
cd Website

# Try importing directly
python -c "import tenant_resolver"
```

### Issue: Configuration not loading

**Fix:**
```python
from tenant_config import get_config_manager
manager = get_config_manager()
print(manager._config)
```

If empty, check:
1. `tenants.json` exists in Website directory
2. File is valid JSON: `python -m json.tool tenants.json`

### Issue: Tests failing

**Fix:**
```bash
# Run with verbose output
pytest test_tenant_system.py -vv

# Run single test
pytest test_tenant_system.py::TestTenantResolver::test_extract_subdomain_valid -v
```

### Issue: Decorators not working

**Fix:**
1. Verify decorators are added ABOVE `@app.route()`
2. Check decorator names match exactly
3. Verify module names match `tenants.json`
4. Restart Flask app after changes

### Issue: 403 but should be allowed

**Fix:**
1. Check tenant resolution: Add debug logging
2. Check module configuration in `tenants.json`
3. Verify module name is spelled correctly
4. Check decorator is actually applied

---

## Performance Testing (Optional)

### Load Test

```python
import requests
import time

start = time.time()
for i in range(100):
    requests.get('http://localhost:4999/', 
                 headers={'X-Tenant-ID': f'tenant-{i%5}'})
elapsed = time.time() - start

print(f"100 requests in {elapsed:.2f}s = {100/elapsed:.0f} req/s")
# Should be > 1000 req/s (tenant system has minimal overhead)
```

### Memory Test

Configuration should use minimal memory:

```python
from tenant_config import get_config_manager
import sys

manager = get_config_manager()
size_bytes = sys.getsizeof(manager._config)
size_kb = size_bytes / 1024

print(f"Configuration size: {size_kb:.2f} KB")
# Should be < 100 KB for typical configuration
```

---

## Sign-Off Checklist

- [ ] All files created and readable
- [ ] Unit tests pass (pytest)
- [ ] Flask app starts without errors
- [ ] Tenant resolution works (curl tests)
- [ ] Configuration loads correctly
- [ ] Error handling works (403 responses)
- [ ] JSON API responses are correct
- [ ] Decorators prevent unauthorized access
- [ ] Decorators allow authorized access
- [ ] Template context available
- [ ] No significant performance impact

**If all checkmarks are ticked, the system is working correctly!** 🎉

---

## Next Steps

1. Add decorators to remaining routes (see TENANT_LINE_NUMBERS.md)
2. Update templates to use module_enabled() checks
3. Customize tenants.json for your specific needs
4. Deploy to production
5. Monitor for issues
