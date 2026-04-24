"""
Jinja2 template helpers for tenant-aware module visibility.

Provides template functions to:
- Check if a module is enabled in templates
- Get list of enabled modules
- Conditionally show UI elements based on module availability
"""

from flask import g
from tenant_config import is_module_enabled, get_enabled_modules


def inject_tenant_context():
    """
    Jinja2 context processor to inject tenant-aware helpers into all templates.
    
    Usage in Flask app setup:
        app.context_processor(inject_tenant_context)
    
    This makes available in templates:
        - module_enabled(module_name) - check if module is enabled
        - enabled_modules - set of enabled module names
        - tenant_id - current tenant identifier
    """
    tenant_id = g.get('tenant_id', 'default')
    
    return {
        'module_enabled': lambda module: is_module_enabled(tenant_id, module),
        'enabled_modules': get_enabled_modules(tenant_id),
        'tenant_id': tenant_id
    }


def module_visible(module_name: str) -> bool:
    """
    Check if a module should be visible in UI (convenience function).
    
    Args:
        module_name: The module name
    
    Returns:
        True if visible/enabled, False otherwise
    """
    return is_module_enabled(g.get('tenant_id', 'default'), module_name)
