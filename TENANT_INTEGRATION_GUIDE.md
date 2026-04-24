# Integration Guide: Adding Tenant Module Guards to Existing Routes

This guide shows exactly where and how to add module guards to existing routes in `main.py`.

## Quick Summary

The system is now partially integrated into `main.py`:
- ✅ Tenant resolution in `before_request` middleware
- ✅ Template context injection
- ✅ 403 error handling
- ⚠️ Routes still need explicit module guards

This document guides you through adding guards to specific routes.

## Module-to-Route Mapping

| Module | Routes | Admin Routes |
|--------|--------|--------------|
| `blog` | `/blog`, `/blog/<post_id>` | `/admin/blog` |
| `chat` | `/chat` | `/admin/chats` |
| `tickets` | `/tickets` | `/admin/tickets` |
| `appointments` | `/appointments`, `/appointments/book-option` | `/admin/appointments/block-day`, `/admin/appointment/<id>` |
| `invoices` | `/my/invoices` | `/admin/invoices` |
| `inventarsystem` | `/inventarsystem` | - |
| `admin` | - | `/admin/*` (all admin routes) |

## Step-by-Step Integration

### 1. Import the Guards

This is **already done** in the updated `main.py`:

```python
from tenant_guards import require_module, require_admin, module_enabled_in_context
```

### 2. Add Route Guards

Find each route in `main.py` and add the appropriate decorator.

#### Example: Blog Module

**Current code** (around line 2402):
```python
@app.route('/blog', methods=['GET', 'POST'])
def blog():
    # ...
```

**Updated code**:
```python
@app.route('/blog', methods=['GET', 'POST'])
@tenant_guards.require_module('blog')
def blog():
    # ...
```

#### Example: Chat Module

**Current code** (around line 2577):
```python
@app.route('/chat', methods=['GET', 'POST'])
def chat():
    # ...
```

**Updated code**:
```python
@app.route('/chat', methods=['GET', 'POST'])
@tenant_guards.require_module('chat')
def chat():
    # ...
```

### 3. Pattern for All Routes

For each route, add the appropriate decorator(s):

```python
# Public feature route
@app.route('/feature-path')
@tenant_guards.require_module('feature_name')
def feature_handler():
    pass

# Admin feature route (requires both admin and specific module)
@app.route('/admin/feature-path')
@tenant_guards.require_admin()
@tenant_guards.require_module('feature_name')
def admin_feature_handler():
    pass
```

## Specific Route Updates

### Blog Routes

**Line ~2402**: Admin blog
```python
@app.route('/admin/blog', methods=['GET', 'POST'])
@tenant_guards.require_admin()
@tenant_guards.require_module('blog')
def admin_blog():
```

**Line ~2480**: Public blog
```python
@app.route('/blog')
@tenant_guards.require_module('blog')
def blog():
```

**Line ~2498**: Blog post detail
```python
@app.route('/blog/<post_id>')
@tenant_guards.require_module('blog')
def blog_post(post_id):
```

### Chat Routes

**Line ~2577**: Chat page
```python
@app.route('/chat', methods=['GET', 'POST'])
@tenant_guards.require_module('chat')
def chat():
```

**Line ~2815**: Admin chats
```python
@app.route('/admin/chats', methods=['GET', 'POST'])
@tenant_guards.require_admin()
@tenant_guards.require_module('chat')
def admin_chats():
```

### Tickets Routes

**Line ~2617**: Tickets
```python
@app.route('/tickets', methods=['GET', 'POST'])
@tenant_guards.require_module('tickets')
def tickets():
```

**Line ~2866**: Admin tickets
```python
@app.route('/admin/tickets', methods=['GET', 'POST'])
@tenant_guards.require_admin()
@tenant_guards.require_module('tickets')
def admin_tickets():
```

### Appointments Routes

**Line ~1742**: Appointments list
```python
@app.route('/appointments', methods=['GET'])
@tenant_guards.require_module('appointments')
def appointments():
```

**Line ~1783**: Book appointment option
```python
@app.route('/appointments/book-option', methods=['POST'])
@tenant_guards.require_module('appointments')
def book_appointment_option():
```

**Line ~2308**: Admin block day
```python
@app.route('/admin/appointments/block-day', methods=['POST'])
@tenant_guards.require_admin()
@tenant_guards.require_module('appointments')
def admin_block_day():
```

**Line ~2357**: Admin manage appointment
```python
@app.route('/admin/appointment/<appointment_id>', methods=['POST'])
@tenant_guards.require_admin()
@tenant_guards.require_module('appointments')
def admin_appointment(appointment_id):
```

### Invoices Routes

**Line ~2523**: My invoices
```python
@app.route('/my/invoices')
@tenant_guards.require_module('invoices')
def my_invoices():
```

**Line ~2913**: Admin invoices
```python
@app.route('/admin/invoices', methods=['GET', 'POST'])
@tenant_guards.require_admin()
@tenant_guards.require_module('invoices')
def admin_invoices():
```

### Admin Routes (ALL require admin module)

All routes under `/admin/*` should have `@tenant_guards.require_admin()`:

- **Line ~1825**: `/admin/dashboard`
- **Line ~1869**: `/admin/instances`
- **Line ~2103**: `/admin/instances/stats`
- **Line ~2110**: `/admin/system`
- **Line ~2191**: `/admin/system/stats`
- **Line ~2198**: `/admin/system/logs/live`
- **Line ~2204**: `/admin/system/logs/core`
- **Line ~2221**: `/admin/system/logs/instance/<subdomain>`
- **Line ~2239**: `/admin/system/backup/export/<subdomain>`
- **Line ~2263**: `/admin/system/backup/import/<subdomain>`
- **Line ~2666**: `/admin/users`
- **Line ~2698**: `/admin/team`

Example:
```python
@app.route('/admin/dashboard')
@tenant_guards.require_admin()
def admin_dashboard():
```

## Template Updates

Update `templates/base.html` or your main navigation template:

### Before
```jinja2
<nav>
  <a href="/blog">Blog</a>
  <a href="/tickets">Tickets</a>
  <a href="/chat">Chat</a>
  <a href="/my/invoices">Invoices</a>
</nav>
```

### After
```jinja2
<nav>
  {% if module_enabled('blog') %}
    <a href="/blog">Blog</a>
  {% endif %}
  
  {% if module_enabled('tickets') %}
    <a href="/tickets">Tickets</a>
  {% endif %}
  
  {% if module_enabled('chat') %}
    <a href="/chat">Chat</a>
  {% endif %}
  
  {% if module_enabled('invoices') %}
    <a href="/my/invoices">Invoices</a>
  {% endif %}
</nav>
```

### Admin Navigation

In admin templates or dashboard, wrap admin sections:

```jinja2
{% if module_enabled('blog') %}
  <li><a href="/admin/blog">Blog Management</a></li>
{% endif %}

{% if module_enabled('chat') %}
  <li><a href="/admin/chats">Chats</a></li>
{% endif %}

{% if module_enabled('tickets') %}
  <li><a href="/admin/tickets">Support Tickets</a></li>
{% endif %}

{% if module_enabled('invoices') %}
  <li><a href="/admin/invoices">Invoices</a></li>
{% endif %}
```

## Testing the Integration

### Test 1: Verify tenant resolution

```bash
# Should resolve to 'default' tenant
curl http://localhost:4999/blog

# Should resolve to 'school1' tenant
curl -H "X-Tenant-ID: school1" http://localhost:4999/chat

# Access denied for school2 chat (disabled)
curl -H "X-Tenant-ID: school2" http://localhost:4999/chat
# Expected: 403 Forbidden
```

### Test 2: Verify route guards

```bash
# Blog is enabled for default, should work
curl http://localhost:4999/blog
# Expected: 200 OK or redirect to login

# Chat is disabled for default, should be forbidden
curl http://localhost:4999/chat
# Expected: 403 Forbidden

# Chat is enabled for school1, should work
curl -H "X-Tenant-ID: school1" http://localhost:4999/chat
# Expected: 200 OK or redirect to login
```

### Test 3: JSON API responses

```bash
# With valid module
curl -H "X-Tenant-ID: school1" \
     -H "Accept: application/json" \
     http://localhost:4999/chat
# Expected: 200 OK with JSON or 302 redirect

# With disabled module
curl -H "X-Tenant-ID: school2" \
     -H "Accept: application/json" \
     http://localhost:4999/chat
# Expected: 403 with JSON error
```

## Implementation Checklist

- [ ] All decorators added to feature routes
- [ ] All decorators added to admin routes
- [ ] Templates updated with `module_enabled()` checks
- [ ] Tested with `curl` or browser
- [ ] Tested 403 error handling
- [ ] Tested JSON API responses
- [ ] Configuration in `tenants.json` verified
- [ ] Environment variable `INSTANCE_PARENT_DOMAIN` set correctly

## Automated Integration (Optional)

If you want to add guards to all routes programmatically, you could:

1. Use a mapping dictionary of module requirements per route
2. Create a loop to add decorators
3. Or manually add as shown in this guide

For now, manual addition ensures you're aware of what each route does and can make informed decisions about module assignments.

## Troubleshooting

### Decorator not working

```python
# Make sure to use the full path if not imported at module level
from tenant_guards import require_module

@app.route('/chat')
@require_module('chat')
def chat():
    pass
```

### 403 template not found

Ensure `templates/error_403.html` exists. If not, create it from `TENANT_CONFIG.md`.

### Module check in template not working

1. Verify `tenant_templates.inject_tenant_context()` is registered as context processor
2. This is **already done** in the updated `main.py`
3. Restart the Flask app to pick up changes

### Routes still accessible when disabled

1. Ensure `@require_module()` decorator is added
2. Check the module name matches in `tenants.json`
3. Verify `INSTANCE_PARENT_DOMAIN` is set correctly for subdomain resolution
4. Check the tenant is resolving correctly: add debug logging to `resolve_tenant_context()`

## Next Steps

1. Add decorators to routes following this guide
2. Update templates to show/hide UI elements
3. Test with multiple tenants
4. Configure `tenants.json` for your specific needs
5. Deploy to production

For detailed information, see [TENANT_CONFIG.md](TENANT_CONFIG.md).
