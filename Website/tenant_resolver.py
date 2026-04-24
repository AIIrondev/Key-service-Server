"""
Tenant resolver for identifying the active tenant from incoming requests.

Supports:
- Subdomain-based tenant detection (e.g., school1.example.com -> school1)
- X-Tenant-ID header for internal APIs and testing
- Fallback to 'default' tenant
"""

import re
from typing import Optional
from flask import request


def extract_subdomain(host: str, parent_domain: str) -> Optional[str]:
    """
    Extract subdomain from host if it matches the parent domain.
    
    Args:
        host: The Host header value (e.g., 'school1.example.com')
        parent_domain: The parent domain (e.g., 'example.com')
    
    Returns:
        The subdomain if found, None otherwise
    """
    if not host or not parent_domain:
        return None
    
    # Remove port if present
    host = host.split(':')[0]
    parent_domain = parent_domain.strip()
    
    # Check if host ends with parent domain
    if not host.endswith(parent_domain):
        return None
    
    # Extract subdomain
    prefix = host[: -len(parent_domain)].rstrip('.')
    
    # Validate subdomain (alphanumeric, hyphens, underscores)
    if prefix and re.match(r'^[a-zA-Z0-9_-]+$', prefix):
        return prefix.lower()
    
    return None


def resolve_tenant(parent_domain: str = "example.com") -> str:
    """
    Resolve the active tenant for the current request.
    
    Resolution order:
    1. X-Tenant-ID header (for APIs and testing)
    2. Subdomain from Host header
    3. Fallback to 'default'
    
    Args:
        parent_domain: The parent domain for subdomain extraction
    
    Returns:
        The tenant identifier (lowercase alphanumeric string)
    """
    # 1. Check X-Tenant-ID header
    tenant_from_header = request.headers.get("X-Tenant-ID", "").strip().lower()
    if tenant_from_header and re.match(r'^[a-zA-Z0-9_-]+$', tenant_from_header):
        return tenant_from_header
    
    # 2. Check subdomain
    host = request.host
    subdomain = extract_subdomain(host, parent_domain)
    if subdomain:
        return subdomain
    
    # 3. Fallback to default
    return "default"
