"""
Route guards and helpers for module-aware access control.

Provides decorators and functions to:
- Protect routes based on module availability
- Return consistent error responses for disabled modules
- Check module availability in views
"""

from functools import wraps
from flask import request, jsonify, abort, g
from typing import Callable, Any
from tenant_config import is_module_enabled, get_enabled_modules


def require_module(module_name: str) -> Callable:
    """
    Decorator to require a module to be enabled for accessing a route.
    
    Usage:
        @app.route('/chat')
        @require_module('chat')
        def chat_endpoint():
            return render_template('chat.html')
    
    Args:
        module_name: The module to check (e.g., 'chat', 'invoices')
    
    Returns:
        Decorator function
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs) -> Any:
            tenant_id = g.get('tenant_id', 'default')
            
            if not is_module_enabled(tenant_id, module_name):
                # For JSON requests, return JSON response
                if request.accept_mimetypes.best_match(['application/json', 'text/html']) == 'application/json':
                    return jsonify({
                        'error': 'Module not available',
                        'message': f'The {module_name} module is not available for your organization.',
                        'module': module_name
                    }), 403
                
                # For HTML requests, return abort with custom message
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_admin() -> Callable:
    """
    Decorator to require admin module to be enabled (and user to be admin).
    
    Usage:
        @app.route('/admin/dashboard')
        @require_admin()
        def admin_dashboard():
            return render_template('admin_dashboard.html')
    
    Returns:
        Decorator function
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs) -> Any:
            tenant_id = g.get('tenant_id', 'default')
            
            # Check if admin module is enabled
            if not is_module_enabled(tenant_id, 'admin'):
                if request.accept_mimetypes.best_match(['application/json', 'text/html']) == 'application/json':
                    return jsonify({
                        'error': 'Admin module not available',
                        'message': 'Admin functionality is not available for your organization.'
                    }), 403
                abort(403)
            
            # Additional user role check (if implemented)
            # This would be combined with existing auth checks
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def module_enabled_in_context(module_name: str) -> bool:
    """
    Check if a module is enabled for the current request context.
    
    Can be used in route handlers and templates (via Jinja2 context).
    
    Args:
        module_name: The module name
    
    Returns:
        True if enabled, False otherwise
    """
    tenant_id = g.get('tenant_id', 'default')
    return is_module_enabled(tenant_id, module_name)


def get_enabled_modules_in_context() -> set:
    """
    Get all enabled modules for the current request context.
    
    Useful for determining which menu items to show, etc.
    
    Returns:
        Set of enabled module names
    """
    tenant_id = g.get('tenant_id', 'default')
    return get_enabled_modules(tenant_id)


class TenantAwareErrorHandler:
    """
    Provides consistent error handling for tenant-specific access issues.
    """
    
    @staticmethod
    def module_not_available(module_name: str, is_json: bool = False):
        """
        Generate error response for disabled module.
        
        Args:
            module_name: The module that is not available
            is_json: Whether to return JSON or HTML
        
        Returns:
            Response tuple (response, status_code)
        """
        if is_json:
            return jsonify({
                'error': 'Module not available',
                'message': f'The {module_name} module is not available for your organization.',
                'module': module_name
            }), 403
        
        abort(403)
    
    @staticmethod
    def unauthorized_access(reason: str = None, is_json: bool = False):
        """
        Generate error response for unauthorized access.
        
        Args:
            reason: Optional reason for the denial
            is_json: Whether to return JSON or HTML
        
        Returns:
            Response tuple (response, status_code)
        """
        if is_json:
            return jsonify({
                'error': 'Access denied',
                'message': reason or 'You do not have access to this resource.'
            }), 403
        
        abort(403)
