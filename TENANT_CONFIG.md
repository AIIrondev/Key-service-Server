# Tenant-Aware Configuration System

This document explains how to use the tenant-aware configuration system for module and feature management in the multi-tenant application.

## Overview

The tenant-aware configuration system allows each tenant (organization/school) to control which modules and features are available to their users. The system supports:

- **Global defaults**: Base configuration applied to all tenants
- **Per-tenant overrides**: Tenant-specific module enables/disables
- **Request-aware checks**: Module availability determined at runtime based on the active request tenant
- **Safe fallbacks**: Missing configurations fail safely to sensible defaults
- **Server-side enforcement**: UI elements and routes protected from unauthorized access

## Architecture

### Components

1. **`tenant_resolver.py`**: Resolves the active tenant from incoming requests
2. **`tenant_config.py`**: Manages configuration loading and module availability checks
3. **`tenant_guards.py`**: Decorators and guards for protecting routes
4. **`tenant_templates.py`**: Jinja2 helpers for template-based module checking
5. **`tenants.json`**: Configuration file with global defaults and per-tenant settings

### Request Flow

```
HTTP Request
    ↓
resolve_tenant_context() [before_request]
    ↓
g.tenant_id = <resolved tenant>
    ↓
Route Handler / Template Rendering
    ↓
module_enabled() / @require_module() checks
    ↓
Allow or Deny access
```

## Configuration

### Configuration File: `tenants.json`

Located in the Website directory alongside `main.py`.

#### Structure

```json
{
  "defaults": {
    "modules": {
      "module_name": true,
      "another_module": false
    }
  },
  "tenants": {
    "tenant_id": {
      "modules": {
        "module_name": false,
        "another_module": true
      }
    }
  }
}
```

#### Interpretation Rules

1. **Global defaults** (`defaults.modules`): Applied to all tenants unless overridden
2. **Tenant overrides**: If a tenant specifies a module, that value is used instead
3. **Missing modules**: If a tenant doesn't specify a module, the global default is used
4. **Safe defaults**: Modules not configured anywhere default to `false` (disabled)

### Example Configuration

```json
{
  "defaults": {
    "modules": {
      "inventarsystem": true,
      "appointments": false,
      "blog": true,
      "chat": false,
      "tickets": false,
      "invoices": false
    }
  },
  "tenants": {
    "school1": {
      "modules": {
        "appointments": true,
        "chat": true,
        "invoices": true
      }
    },
    "school2": {
      "modules": {
        "appointments": true,
        "blog": false,
        "chat": false
      }
    }
  }
}
```

In this example:
- **School 1**: Has appointments, chat, and invoices enabled (plus blog from defaults). No tickets.
- **School 2**: Has appointments enabled (plus inventarsystem and blog from defaults). No chat or tickets.

## Tenant Resolution

### Resolution Order

The system tries to resolve the tenant in this order:

1. **X-Tenant-ID header**: For internal APIs and testing
   ```bash
   curl -H "X-Tenant-ID: school1" https://api.example.com/chat
   ```

2. **Subdomain**: Based on the Host header (e.g., `school1.example.com` → `school1`)
   ```
   school1.example.com/chat  →  tenant_id = "school1"
   www.example.com/chat      →  tenant_id = "default"
   ```

3. **Fallback**: Uses `"default"` if no tenant can be resolved

### Configuration

The parent domain for subdomain extraction is set via environment variable:

```bash
export INSTANCE_PARENT_DOMAIN="example.com"
```

## Usage

### In Route Handlers

#### Basic Module Check

```python
from flask import g
from tenant_config import is_module_enabled

@app.route('/chat')
def chat_page():
    if not is_module_enabled(g.tenant_id, 'chat'):
        abort(403)
    return render_template('chat.html')
```

#### Using Decorators

```python
from tenant_guards import require_module, require_admin

@app.route('/chat')
@require_module('chat')
def chat_page():
    return render_template('chat.html')

@app.route('/admin/dashboard')
@require_admin()
def admin_dashboard():
    return render_template('admin_dashboard.html')
```

#### Getting Enabled Modules

```python
from tenant_config import get_enabled_modules

@app.route('/api/features')
def get_features():
    modules = get_enabled_modules(g.tenant_id)
    return jsonify({'enabled_modules': list(modules)})
```

### In Templates

Use the context variables injected by `inject_tenant_context()`:

#### Check Single Module

```jinja2
{% if module_enabled('chat') %}
  <li><a href="/chat">Chat</a></li>
{% endif %}
```

#### Show Multiple Navigation Items

```jinja2
<nav>
  {% if module_enabled('blog') %}
    <li><a href="/blog">Blog</a></li>
  {% endif %}
  
  {% if module_enabled('tickets') %}
    <li><a href="/tickets">Support</a></li>
  {% endif %}
  
  {% if module_enabled('invoices') %}
    <li><a href="/my/invoices">Rechnungen</a></li>
  {% endif %}
</nav>
```

#### Get All Enabled Modules

```jinja2
<div class="features">
  {% for module in enabled_modules %}
    <span class="badge">{{ module }}</span>
  {% endfor %}
</div>
```

#### Display Current Tenant

```jinja2
<footer>
  Tenant: {{ tenant_id }}
</footer>
```

### In API Endpoints

```python
@app.route('/api/features', methods=['GET'])
def api_features():
    tenant_id = g.tenant_id
    
    if request.accept_mimetypes.best_match(['application/json']) != 'application/json':
        abort(406)
    
    # Check module availability for JSON response
    if not is_module_enabled(tenant_id, 'chat'):
        return jsonify({
            'error': 'Module not available',
            'message': 'The chat module is not available for your organization.'
        }), 403
    
    return jsonify({'status': 'ok'})
```

## Integration Points

### Existing Routes to Update

To complete the integration, routes for disabled modules should check availability:

1. **`/chat`** - Add `@require_module('chat')`
2. **`/tickets`** - Add `@require_module('tickets')`
3. **`/admin/invoices`** - Add `@require_module('invoices')` + `@require_admin()`
4. **`/blog`** - Add `@require_module('blog')`
5. **`/appointments`** - Add `@require_module('appointments')`
6. **`/admin/chats`** - Add `@require_module('chat')` + `@require_admin()`
7. **`/admin/tickets`** - Add `@require_module('tickets')` + `@require_admin()`

### Templates to Update

Navigation templates (`base.html`, `admin_dashboard.html`, etc.) should use:

```jinja2
{% if module_enabled('module_name') %}
  <!-- Show UI element -->
{% endif %}
```

## Runtime Behavior

### Disabled Module Access

When a user tries to access a disabled module:

#### HTML Requests
- Route returns HTTP 403 Forbidden
- User sees `error_403.html` template

#### JSON Requests
- Route returns HTTP 403 with JSON error response:
```json
{
  "error": "Module not available",
  "message": "The chat module is not available for your organization.",
  "module": "chat"
}
```

### Direct URL Access

Protected routes reject direct access when modules are disabled, preventing workarounds.

### Safe Defaults

- Missing tenant configurations inherit global defaults
- Invalid tenant IDs fall back to 'default' tenant
- Modules not configured anywhere default to disabled
- The system remains stable even if `tenants.json` is missing

## Adding New Modules

### Step 1: Add to Configuration

Edit `tenants.json`:

```json
{
  "defaults": {
    "modules": {
      "new_feature": true
    }
  },
  "tenants": {
    "school1": {
      "modules": {
        "new_feature": false
      }
    }
  }
}
```

### Step 2: Add Route Guard

```python
@app.route('/new-feature')
@require_module('new_feature')
def new_feature():
    return render_template('new_feature.html')
```

### Step 3: Update Templates

```jinja2
{% if module_enabled('new_feature') %}
  <li><a href="/new-feature">New Feature</a></li>
{% endif %}
```

## Configuration Management

### Reloading Configuration

The configuration is loaded at application startup. To reload without restarting:

```python
from tenant_config import get_config_manager

manager = get_config_manager()
manager.reload()
```

### Accessing Configuration Programmatically

```python
from tenant_config import get_config_manager

manager = get_config_manager()

# Get complete tenant config (merged with defaults)
config = manager.get_tenant_config('school1')

# Get all enabled modules for a tenant
modules = manager.get_enabled_modules('school1')

# Get a specific config value
value = manager.get_config_value('school1', 'custom_setting', default='fallback')

# Get all modules defined in configuration
all_modules = manager.get_all_modules()
```

## Testing

### Testing with curl

```bash
# Test without tenant header (uses default)
curl http://example.com/chat

# Test with X-Tenant-ID header
curl -H "X-Tenant-ID: school1" http://example.com/chat

# Test with subdomain
curl http://school1.example.com/chat

# Check features endpoint
curl -H "X-Tenant-ID: school1" http://example.com/api/features
```

### Testing in Python

```python
from tenant_resolver import resolve_tenant, extract_subdomain
from tenant_config import is_module_enabled, get_enabled_modules

# Test subdomain extraction
assert extract_subdomain("school1.example.com", "example.com") == "school1"
assert extract_subdomain("www.example.com", "example.com") == "www"
assert extract_subdomain("example.com", "example.com") is None

# Test module availability
assert is_module_enabled("school1", "chat") == True
assert is_module_enabled("school2", "chat") == False
```

## Error Handling

The system handles these error cases gracefully:

1. **Missing `tenants.json`**: Uses empty configuration with safe defaults
2. **Malformed JSON**: Logs error, uses empty configuration
3. **Invalid tenant ID**: Falls back to 'default' tenant
4. **Missing module config**: Defaults to disabled (safe default)
5. **Missing tenant section**: Inherits all global defaults
6. **Invalid module values**: Treated as disabled

## Security Notes

- Module checks are **enforced server-side** on every request
- UI elements are hidden, but routes are protected
- Users cannot bypass disabled modules through direct URL access
- API endpoints return consistent 403 responses for disabled modules
- Tenant resolution supports both internal headers and public subdomains
- Configuration is read-only at runtime (safe from modification)

## Best Practices

1. **Always use decorators** for route protection
2. **Hide UI elements** in templates when modules are disabled
3. **Return consistent errors** for disabled modules
4. **Test tenant switching** to ensure proper isolation
5. **Keep defaults conservative** and override with caution
6. **Document custom modules** in `tenants.json` comments
7. **Monitor module availability** in user-facing error messages
8. **Version control `tenants.json`** for production deployments

## Troubleshooting

### Module appears disabled but shouldn't be

1. Check `tenants.json` for correct tenant ID spelling
2. Verify `INSTANCE_PARENT_DOMAIN` environment variable
3. Confirm tenant is resolving correctly (check `g.tenant_id`)
4. Reload configuration if recently changed

### Tenant not resolving correctly

1. Check X-Tenant-ID header format
2. Verify subdomain matches parent domain
3. Confirm no port conflicts in Host header
4. Check request logs for resolution details

### Configuration changes not taking effect

1. Config is loaded at startup only
2. Restart application to reload `tenants.json`
3. Or call `get_config_manager().reload()`

## Example: Complete Integration

See the default configuration in `tenants.json` for a working example with:
- Global defaults for common modules
- School tenant with full features
- Partner organization with limited features
