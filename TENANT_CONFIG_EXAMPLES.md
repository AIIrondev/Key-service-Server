# Tenant Configuration Examples

This document provides practical examples of tenant configurations for different scenarios.

## Example 1: Education Provider with Multiple Schools

Each school gets different features based on their subscription level.

```json
{
  "defaults": {
    "modules": {
      "inventarsystem": true,
      "appointments": false,
      "blog": true,
      "chat": false,
      "tickets": false,
      "invoices": false,
      "dienstleistungen": true,
      "projekte": true,
      "team": true,
      "kontakt": true,
      "admin": false
    }
  },
  "tenants": {
    "gymnasium-berlin": {
      "description": "Premium school - all features",
      "modules": {
        "inventarsystem": true,
        "appointments": true,
        "blog": true,
        "chat": true,
        "tickets": true,
        "invoices": true,
        "dienstleistungen": false,
        "projekte": false,
        "team": true,
        "admin": true
      }
    },
    "realschule-munich": {
      "description": "Standard school - core features",
      "modules": {
        "inventarsystem": true,
        "appointments": true,
        "blog": false,
        "chat": false,
        "tickets": true,
        "invoices": false,
        "dienstleistungen": false,
        "projekte": false,
        "team": true,
        "admin": true
      }
    },
    "grundschule-hamburg": {
      "description": "Basic school - inventory only",
      "modules": {
        "inventarsystem": true,
        "appointments": false,
        "blog": false,
        "chat": false,
        "tickets": false,
        "invoices": false,
        "dienstleistungen": false,
        "projekte": false,
        "team": false,
        "admin": false
      }
    }
  }
}
```

**Result:**
- Gymnasium Berlin: Full access to all features
- Realschule Munich: Inventory, appointments, tickets, team management
- Grundschule Hamburg: Inventory system only (read-only or restricted admin)

---

## Example 2: SaaS Multi-Tenant Platform

Supporting different customer types with appropriate feature sets.

```json
{
  "defaults": {
    "modules": {
      "inventarsystem": true,
      "appointments": false,
      "blog": false,
      "chat": false,
      "tickets": false,
      "invoices": false,
      "dienstleistungen": false,
      "projekte": false,
      "team": true,
      "kontakt": true,
      "admin": false
    }
  },
  "tenants": {
    "startup-acme": {
      "description": "Startup plan - minimal features",
      "modules": {
        "invoices": true,
        "admin": true
      }
    },
    "enterprise-bigcorp": {
      "description": "Enterprise plan - all features",
      "modules": {
        "inventarsystem": true,
        "appointments": true,
        "blog": true,
        "chat": true,
        "tickets": true,
        "invoices": true,
        "team": true,
        "admin": true
      }
    },
    "agency-webdesign": {
      "description": "Agency plan - client-facing features",
      "modules": {
        "blog": true,
        "chat": true,
        "appointments": true,
        "invoices": true,
        "tickets": true,
        "team": true,
        "admin": true
      }
    }
  }
}
```

**Result:**
- Startup: Only invoicing and basic admin
- Enterprise: Complete platform access
- Agency: Client-facing + internal management

---

## Example 3: Regional Service Provider

Different regions/branches get different feature access.

```json
{
  "defaults": {
    "modules": {
      "inventarsystem": false,
      "appointments": true,
      "blog": true,
      "chat": true,
      "tickets": true,
      "invoices": true,
      "dienstleistungen": true,
      "projekte": true,
      "team": true,
      "kontakt": true,
      "admin": false
    }
  },
  "tenants": {
    "branch-north": {
      "description": "Northern branch - full service",
      "modules": {
        "admin": true,
        "invoices": true
      }
    },
    "branch-south": {
      "description": "Southern branch - no invoicing yet",
      "modules": {
        "admin": true,
        "invoices": false
      }
    },
    "branch-east": {
      "description": "Eastern branch - new, limited services",
      "modules": {
        "appointments": false,
        "tickets": false,
        "chat": false,
        "invoices": false,
        "admin": false
      }
    }
  }
}
```

**Result:**
- North: Full platform with invoicing
- South: Full platform except invoicing
- East: Limited to blog, services, projects, team, contact

---

## Example 4: Progressive Rollout

Enable features gradually for tenants during pilot periods.

```json
{
  "defaults": {
    "modules": {
      "inventarsystem": true,
      "appointments": false,
      "blog": true,
      "chat": false,
      "tickets": false,
      "invoices": false,
      "dienstleistungen": true,
      "projekte": true,
      "team": true,
      "kontakt": true,
      "admin": false
    }
  },
  "tenants": {
    "pilot-tenant-1": {
      "description": "Pilot for chat feature",
      "modules": {
        "chat": true,
        "admin": true
      }
    },
    "pilot-tenant-2": {
      "description": "Pilot for tickets and invoices",
      "modules": {
        "tickets": true,
        "invoices": true,
        "admin": true
      }
    },
    "general-users": {
      "description": "Not in any pilot - uses defaults",
      "modules": {}
    }
  }
}
```

**Result:**
- Pilot Tenant 1: Testing chat feature + admin
- Pilot Tenant 2: Testing tickets and invoicing
- General Users: Standard feature set (defaults)

---

## Example 5: Partner/Vendor Access

External partners with limited, specific access.

```json
{
  "defaults": {
    "modules": {
      "inventarsystem": false,
      "appointments": false,
      "blog": false,
      "chat": false,
      "tickets": false,
      "invoices": false,
      "dienstleistungen": true,
      "projekte": true,
      "team": true,
      "kontakt": true,
      "admin": false
    }
  },
  "tenants": {
    "partner-logistics": {
      "description": "Logistics partner - can manage appointments",
      "modules": {
        "appointments": true,
        "chat": true,
        "admin": true
      }
    },
    "partner-support": {
      "description": "Support partner - can manage tickets",
      "modules": {
        "tickets": true,
        "chat": true,
        "admin": true
      }
    },
    "partner-billing": {
      "description": "Billing partner - can manage invoices",
      "modules": {
        "invoices": true,
        "chat": true,
        "admin": true
      }
    }
  }
}
```

**Result:**
- Logistics Partner: Appointments, chat, limited admin
- Support Partner: Tickets, chat, limited admin
- Billing Partner: Invoices, chat, limited admin

---

## Example 6: Feature Flags for A/B Testing

Use tenant config as feature flags for experiments.

```json
{
  "defaults": {
    "modules": {
      "inventarsystem": true,
      "appointments": false,
      "blog": true,
      "chat": false,
      "tickets": false,
      "invoices": false,
      "dienstleistungen": true,
      "projekte": true,
      "team": true,
      "kontakt": true,
      "admin": false,
      "new_dashboard": false,
      "advanced_reporting": false
    }
  },
  "tenants": {
    "test-group-a": {
      "description": "A/B test group A - new UI enabled",
      "modules": {
        "new_dashboard": true,
        "admin": true
      }
    },
    "test-group-b": {
      "description": "A/B test group B - advanced reporting",
      "modules": {
        "advanced_reporting": true,
        "admin": true
      }
    }
  }
}
```

**Result:**
- Test Group A: Can see and test new dashboard
- Test Group B: Can see and test advanced reporting
- Default: Standard interface

---

## Configuration Patterns

### Pattern 1: Additive (Start Minimal, Add Features)

```json
{
  "defaults": {
    "modules": { "all": false }
  },
  "tenants": {
    "customer1": {
      "modules": {
        "feature_x": true,
        "feature_y": true
      }
    }
  }
}
```

**Best for:** Platforms where most customers get limited features

---

### Pattern 2: Subtractive (Start Full, Remove Features)

```json
{
  "defaults": {
    "modules": { "all": true }
  },
  "tenants": {
    "limited_customer": {
      "modules": {
        "premium_feature": false,
        "advanced_reporting": false
      }
    }
  }
}
```

**Best for:** Platforms where most customers get full access

---

### Pattern 3: Hybrid (Different Defaults by Context)

```json
{
  "defaults": {
    "modules": {
      "core_feature": true,
      "premium_feature": false,
      "beta_feature": false
    }
  },
  "tenants": {
    "premium_customer": {
      "modules": {
        "premium_feature": true,
        "beta_feature": true
      }
    },
    "basic_customer": {
      "modules": {}
    }
  }
}
```

**Best for:** Most platforms with mixed customer types

---

## Testing Configurations

### Quick Test Setup

```json
{
  "defaults": {
    "modules": {
      "inventarsystem": true,
      "appointments": true,
      "blog": true,
      "chat": true,
      "tickets": true,
      "invoices": true,
      "admin": true
    }
  },
  "tenants": {
    "test-all-enabled": {
      "modules": {}
    },
    "test-all-disabled": {
      "modules": {
        "inventarsystem": false,
        "appointments": false,
        "blog": false,
        "chat": false,
        "tickets": false,
        "invoices": false,
        "admin": false
      }
    }
  }
}
```

### Load Testing with Multiple Tenants

```json
{
  "defaults": {
    "modules": { "inventarsystem": true }
  },
  "tenants": {
    "load-tenant-1": {},
    "load-tenant-2": {},
    "load-tenant-3": {},
    "load-tenant-4": {},
    "load-tenant-5": {}
  }
}
```

---

## Migration Examples

### From Hardcoded Checks to Config

**Before:**
```python
def chat():
    if current_user.organization_id != "school1":
        abort(403)
    return render_template('chat.html')
```

**After:**
```python
@app.route('/chat')
@require_module('chat')
def chat():
    return render_template('chat.html')
```

Config in `tenants.json`:
```json
{
  "tenants": {
    "school1": {
      "modules": { "chat": true }
    }
  }
}
```

---

## Best Practices for Configuration

1. **Start conservative**: Disable modules by default, enable per tenant
2. **Document decisions**: Add `"description"` fields explaining why
3. **Use consistent naming**: Module names should match route/feature names
4. **Version your config**: Keep `tenants.json` in version control
5. **Test thoroughly**: Use test tenants for new features
6. **Monitor usage**: Track which modules are actually used per tenant
7. **Plan migrations**: Have a strategy for upgrading tenants
8. **Document changes**: Comment when enabling/disabling modules

---

## Accessing Configuration Programmatically

```python
from tenant_config import get_config_manager

manager = get_config_manager()

# Print all enabled modules for school1
config = manager.get_tenant_config('school1')
print(config['modules'])

# Check if specific module is enabled
if manager.is_module_enabled('school1', 'chat'):
    print("Chat is enabled for school1")

# Get all tenants with chat enabled
all_modules = manager.get_all_modules()
for module in all_modules:
    print(f"Module: {module}")
```

---

## Debugging Configuration Issues

```bash
# Print current configuration
python3 -c "
from tenant_config import get_config_manager
import json

manager = get_config_manager()
print('school1 config:')
print(json.dumps(manager.get_tenant_config('school1'), indent=2))

print('Enabled modules:')
print(manager.get_enabled_modules('school1'))

print('All modules in config:')
print(manager.get_all_modules())
"
```

---

## Performance Considerations

- Configuration is loaded once at startup
- Module checks are O(1) dictionary lookups
- Safe to call frequently in route handlers
- Consider caching results if checking many tenants in a loop

For production deployments, monitor configuration reload times and cache
appropriately if configuration changes frequently.
