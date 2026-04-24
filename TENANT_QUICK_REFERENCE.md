# Tenant System - Quick Reference Card

## For Developers: How to Protect a Route

### Option 1: Require Specific Module
```python
@app.route('/chat')
@tenant_guards.require_module('chat')
def chat():
    return render_template('chat.html')
```

### Option 2: Require Admin Access
```python
@app.route('/admin/dashboard')
@tenant_guards.require_admin()
def admin_dashboard():
    return render_template('admin_dashboard.html')
```

### Option 3: Manual Check in Handler
```python
from flask import g
from tenant_config import is_module_enabled

@app.route('/feature')
def feature():
    if not is_module_enabled(g.tenant_id, 'feature'):
        abort(403)
    return render_template('feature.html')
```

## For Template Authors: Show/Hide UI

```jinja2
<!-- Check single module -->
{% if module_enabled('chat') %}
  <a href="/chat">Chat</a>
{% endif %}

<!-- Check multiple -->
{% if module_enabled('blog') or module_enabled('news') %}
  <section>News & Updates</section>
{% endif %}

<!-- Loop through enabled -->
{% for module in enabled_modules %}
  {{ module }}
{% endfor %}

<!-- Get current tenant -->
Current tenant: {{ tenant_id }}
```

## For Configuration: tenants.json

```json
{
  "defaults": {
    "modules": {
      "chat": true,
      "blog": false
    }
  },
  "tenants": {
    "school1": {
      "modules": {
        "chat": false
      }
    }
  }
}
```

**Rules:**
- Global `defaults.modules` applies to all tenants
- Tenant can override any module
- If tenant doesn't specify a module, it inherits the default
- Missing everywhere = disabled (safe default)

## Tenant Resolution

1. **X-Tenant-ID header** (highest priority)
   ```bash
   curl -H "X-Tenant-ID: school1" http://example.com/api
   ```

2. **Subdomain** (from Host header)
   ```
   school1.example.com → tenant_id = "school1"
   ```

3. **Fallback** (lowest priority)
   ```
   example.com → tenant_id = "default"
   ```

## Testing

```bash
# Test with specific tenant
curl -H "X-Tenant-ID: school1" http://localhost:4999/chat

# Test forbidden response
curl -H "X-Tenant-ID: school2" http://localhost:4999/chat
# Returns: 403 Forbidden

# Test JSON API
curl -H "X-Tenant-ID: school1" \
     -H "Accept: application/json" \
     http://localhost:4999/chat
# Returns: 200 OK (if allowed) or 403 with JSON error
```

## Configuration Access in Code

```python
from tenant_config import (
    is_module_enabled,
    get_enabled_modules,
    get_tenant_config,
    get_config_manager
)
from flask import g

# Check single module
if is_module_enabled(g.tenant_id, 'chat'):
    # Module is enabled

# Get all enabled modules
modules = get_enabled_modules(g.tenant_id)  # Returns set

# Get full config
config = get_tenant_config(g.tenant_id)  # Returns dict

# Advanced: use manager directly
manager = get_config_manager()
manager.reload()  # Reload from disk
```

## Environment Variables

```bash
# Set parent domain for subdomain extraction
export INSTANCE_PARENT_DOMAIN="example.com"
```

## Common Module Names

- `inventarsystem` - Inventory management
- `appointments` - Appointment booking
- `blog` - Blog/news system
- `chat` - Chat/messaging
- `tickets` - Support tickets
- `invoices` - Invoice management
- `admin` - Admin panel
- `dienstleistungen` - Services
- `projekte` - Projects
- `team` - Team management
- `kontakt` - Contact forms

## Error Responses

**HTML Response (403):**
```
HTTP/1.1 403 Forbidden
Content-Type: text/html

[Rendered error_403.html template]
```

**JSON Response (403):**
```json
{
  "error": "Module not available",
  "message": "The chat module is not available for your organization.",
  "module": "chat"
}
```

## Integration Checklist

- [ ] Import tenant modules at top of main.py
- [ ] Add @require_module() decorators to feature routes
- [ ] Add @require_admin() to admin routes  
- [ ] Update templates with module_enabled() checks
- [ ] Set INSTANCE_PARENT_DOMAIN environment variable
- [ ] Test with curl/browser
- [ ] Run pytest test_tenant_system.py
- [ ] Review tenants.json configuration

## Debugging

Add to main.py for debug output:
```python
@app.before_request
def debug_request():
    print(f"Tenant: {g.tenant_id}")
    print(f"Host: {request.host}")
    print(f"Headers: {dict(request.headers)}")
```

Check if module is working:
```python
from tenant_config import get_config_manager
manager = get_config_manager()
config = manager.get_tenant_config('school1')
print(config)
```

## Key Files

- **`tenant_resolver.py`** - Tenant detection
- **`tenant_config.py`** - Configuration management
- **`tenant_guards.py`** - Route decorators
- **`tenant_templates.py`** - Template helpers
- **`tenants.json`** - Configuration file
- **`main.py`** - Integration point (partially done)
- **`test_tenant_system.py`** - Unit tests

## What's Automatic

✅ Tenant resolution from request
✅ 403 error handling
✅ Template context injection
✅ Configuration loading

## What You Need To Do

⚠️ Add @require_module() to routes
⚠️ Add module_enabled() checks to templates
⚠️ Configure tenants.json

## Documentation

- **`TENANT_CONFIG.md`** - Complete reference
- **`TENANT_INTEGRATION_GUIDE.md`** - Step-by-step
- **`TENANT_CONFIG_EXAMPLES.md`** - Real examples
- **`TENANT_IMPLEMENTATION_SUMMARY.md`** - Overview
- **This file** - Quick reference

## Support

**Q: How do I add a new module?**
A: Add to tenants.json defaults, add decorator to route, add check to template.

**Q: Can I change configuration without restarting?**
A: Call `get_config_manager().reload()` in production.

**Q: How do I test different tenants?**
A: Use X-Tenant-ID header or different subdomains.

**Q: Is this enforced server-side?**
A: Yes, routes reject requests before rendering templates.

**Q: Can users bypass disabled modules?**
A: No, they get 403 on direct URL access.
