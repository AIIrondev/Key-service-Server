"""
Tenant-aware configuration system for module and feature management.

Supports:
- Global default module configuration
- Per-tenant overrides
- Runtime module availability checks
- Safe fallback to defaults for missing configurations
"""

import os
import json
import logging
from typing import Any, Dict, Optional, Set
from pathlib import Path

logger = logging.getLogger(__name__)


class TenantConfigManager:
    """
    Manages tenant-specific configurations with global defaults and per-tenant overrides.
    """
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize the tenant config manager.
        
        Args:
            config_file: Path to the tenants.json configuration file.
                        If not provided, defaults to tenants.json in the same directory.
        """
        if config_file is None:
            config_file = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "tenants.json"
            )
        
        self.config_file = config_file
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from tenants.json file."""
        try:
            if not os.path.exists(self.config_file):
                logger.warning(f"Config file not found: {self.config_file}. Using empty defaults.")
                self._config = {"defaults": {"modules": {}}, "tenants": {}}
                return
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
            
            # Ensure required sections exist
            if "defaults" not in self._config:
                self._config["defaults"] = {}
            if "modules" not in self._config["defaults"]:
                self._config["defaults"]["modules"] = {}
            if "tenants" not in self._config:
                self._config["tenants"] = {}
            
            logger.info(f"Loaded tenant configuration from {self.config_file}")
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            self._config = {"defaults": {"modules": {}}, "tenants": {}}
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
            self._config = {"defaults": {"modules": {}}, "tenants": {}}
    
    def reload(self) -> None:
        """Reload configuration from file."""
        self._load_config()
    
    def get_tenant_config(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get the complete configuration for a tenant (merged with defaults).
        
        Args:
            tenant_id: The tenant identifier
        
        Returns:
            Dict with tenant configuration, including inherited defaults
        """
        # Validate tenant_id
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            return self._get_default_config()
        
        tenant_id = tenant_id.lower().strip()
        
        # Get tenant-specific config if it exists
        tenant_config = self._config.get("tenants", {}).get(tenant_id, {})
        
        # Start with defaults
        merged = {
            "modules": dict(self._config.get("defaults", {}).get("modules", {}))
        }
        
        # Merge tenant-specific module overrides
        if "modules" in tenant_config:
            merged["modules"].update(tenant_config.get("modules", {}))
        
        # Include any other tenant-specific settings
        for key in tenant_config:
            if key != "modules":
                merged[key] = tenant_config[key]
        
        return merged
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get the default configuration."""
        return {
            "modules": dict(self._config.get("defaults", {}).get("modules", {}))
        }
    
    def is_module_enabled(self, tenant_id: str, module_name: str) -> bool:
        """
        Check if a module is enabled for a specific tenant.
        
        Args:
            tenant_id: The tenant identifier
            module_name: The module name (e.g., 'library', 'chat', 'appointments')
        
        Returns:
            True if the module is enabled, False otherwise
        """
        if not isinstance(module_name, str) or not module_name.strip():
            return False
        
        config = self.get_tenant_config(tenant_id)
        modules = config.get("modules", {})
        
        # If module is explicitly configured, use that value
        if module_name in modules:
            enabled = modules[module_name]
            return enabled is True or (isinstance(enabled, dict) and enabled.get("enabled", False) is True)
        
        # If not configured, default to False (fail-safe for optional features)
        return False
    
    def get_enabled_modules(self, tenant_id: str) -> Set[str]:
        """
        Get the set of enabled modules for a tenant.
        
        Args:
            tenant_id: The tenant identifier
        
        Returns:
            Set of enabled module names
        """
        config = self.get_tenant_config(tenant_id)
        modules = config.get("modules", {})
        
        enabled = set()
        for module_name, module_config in modules.items():
            if module_config is True:
                enabled.add(module_name)
            elif isinstance(module_config, dict) and module_config.get("enabled", False) is True:
                enabled.add(module_name)
        
        return enabled
    
    def get_all_modules(self) -> Set[str]:
        """
        Get all module names defined in the configuration.
        
        Returns:
            Set of all module names
        """
        all_modules = set()
        
        # Add modules from defaults
        all_modules.update(self._config.get("defaults", {}).get("modules", {}).keys())
        
        # Add modules from tenants
        for tenant_config in self._config.get("tenants", {}).values():
            all_modules.update(tenant_config.get("modules", {}).keys())
        
        return all_modules
    
    def get_config_value(self, tenant_id: str, key: str, default: Any = None) -> Any:
        """
        Get a tenant-specific configuration value with fallback to default.
        
        Args:
            tenant_id: The tenant identifier
            key: The configuration key
            default: The default value if not found
        
        Returns:
            The configuration value or default
        """
        config = self.get_tenant_config(tenant_id)
        return config.get(key, default)


# Global instance (lazy loaded)
_manager: Optional[TenantConfigManager] = None


def get_config_manager() -> TenantConfigManager:
    """Get or create the global config manager instance."""
    global _manager
    if _manager is None:
        _manager = TenantConfigManager()
    return _manager


def is_module_enabled(tenant_id: str, module_name: str) -> bool:
    """
    Check if a module is enabled for a tenant (convenience function).
    
    Args:
        tenant_id: The tenant identifier
        module_name: The module name
    
    Returns:
        True if enabled, False otherwise
    """
    return get_config_manager().is_module_enabled(tenant_id, module_name)


def get_tenant_config(tenant_id: str) -> Dict[str, Any]:
    """
    Get tenant configuration (convenience function).
    
    Args:
        tenant_id: The tenant identifier
    
    Returns:
        The tenant configuration dict
    """
    return get_config_manager().get_tenant_config(tenant_id)


def get_enabled_modules(tenant_id: str) -> Set[str]:
    """
    Get enabled modules for a tenant (convenience function).
    
    Args:
        tenant_id: The tenant identifier
    
    Returns:
        Set of enabled module names
    """
    return get_config_manager().get_enabled_modules(tenant_id)
