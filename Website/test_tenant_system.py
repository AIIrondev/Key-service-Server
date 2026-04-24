"""
Unit tests for the tenant-aware configuration system.

Run with: pytest test_tenant_system.py -v
"""

import pytest
import json
import tempfile
import os
from pathlib import Path

# Test imports
from tenant_resolver import resolve_tenant, extract_subdomain
from tenant_config import (
    TenantConfigManager,
    is_module_enabled,
    get_config_manager,
    get_enabled_modules,
    get_tenant_config,
)


class TestTenantResolver:
    """Tests for tenant resolution from requests."""
    
    def test_extract_subdomain_valid(self):
        """Test extracting valid subdomain."""
        assert extract_subdomain("school1.example.com", "example.com") == "school1"
        assert extract_subdomain("my-tenant.example.com", "example.com") == "my-tenant"
        assert extract_subdomain("tenant_1.example.com", "example.com") == "tenant_1"
    
    def test_extract_subdomain_with_port(self):
        """Test subdomain extraction with port number."""
        assert extract_subdomain("school1.example.com:8080", "example.com") == "school1"
        assert extract_subdomain("example.com:443", "example.com") is None
    
    def test_extract_subdomain_invalid(self):
        """Test invalid subdomain extraction."""
        assert extract_subdomain("example.com", "example.com") is None
        assert extract_subdomain("other.com", "example.com") is None
        assert extract_subdomain("", "example.com") is None
        # Subdomain with invalid characters
        assert extract_subdomain("invalid@sub.example.com", "example.com") is None
        assert extract_subdomain("invalid#sub.example.com", "example.com") is None
    
    def test_extract_subdomain_case_insensitive(self):
        """Test that subdomains are normalized to lowercase."""
        result = extract_subdomain("SCHOOL1.example.com", "example.com")
        assert result == "school1"  # Should be lowercase


class TestTenantConfigManager:
    """Tests for tenant configuration management."""
    
    @pytest.fixture
    def config_file(self):
        """Create a temporary config file for testing."""
        config = {
            "defaults": {
                "modules": {
                    "chat": True,
                    "blog": False,
                    "tickets": False,
                    "invoices": False,
                }
            },
            "tenants": {
                "tenant_a": {
                    "modules": {
                        "chat": False,
                        "blog": True,
                    }
                },
                "tenant_b": {
                    "modules": {
                        "invoices": True,
                    }
                },
            }
        }
        
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(config, f)
            yield path
        finally:
            os.unlink(path)
    
    def test_load_config(self, config_file):
        """Test loading configuration from file."""
        manager = TenantConfigManager(config_file)
        assert "defaults" in manager._config
        assert "tenants" in manager._config
        assert "tenant_a" in manager._config["tenants"]
    
    def test_missing_config_file(self):
        """Test handling of missing configuration file."""
        manager = TenantConfigManager("/nonexistent/path/tenants.json")
        # Should create empty config with safe defaults
        assert manager._config == {"defaults": {"modules": {}}, "tenants": {}}
    
    def test_get_tenant_config_with_defaults(self, config_file):
        """Test getting tenant config with defaults merged."""
        manager = TenantConfigManager(config_file)
        
        # Tenant A overrides some modules
        config_a = manager.get_tenant_config("tenant_a")
        assert config_a["modules"]["chat"] == False  # Override
        assert config_a["modules"]["blog"] == True   # Override
        assert config_a["modules"]["tickets"] == False  # From default
    
    def test_get_tenant_config_inherits_defaults(self, config_file):
        """Test that tenant inherits all defaults."""
        manager = TenantConfigManager(config_file)
        
        # Tenant B has minimal overrides
        config_b = manager.get_tenant_config("tenant_b")
        assert config_b["modules"]["chat"] == True  # From default
        assert config_b["modules"]["blog"] == False  # From default
        assert config_b["modules"]["invoices"] == True  # Override
    
    def test_get_tenant_config_missing_tenant(self, config_file):
        """Test getting config for non-existent tenant."""
        manager = TenantConfigManager(config_file)
        
        config = manager.get_tenant_config("nonexistent_tenant")
        # Should inherit all defaults
        assert config["modules"]["chat"] == True
        assert config["modules"]["blog"] == False
    
    def test_is_module_enabled_default_true(self, config_file):
        """Test module enabled when default is true."""
        manager = TenantConfigManager(config_file)
        
        # chat is enabled by default
        assert manager.is_module_enabled("tenant_c", "chat") == True
    
    def test_is_module_enabled_default_false(self, config_file):
        """Test module disabled when default is false."""
        manager = TenantConfigManager(config_file)
        
        # blog is disabled by default
        assert manager.is_module_enabled("tenant_c", "blog") == False
    
    def test_is_module_enabled_override(self, config_file):
        """Test module override by tenant."""
        manager = TenantConfigManager(config_file)
        
        # tenant_a overrides chat to false
        assert manager.is_module_enabled("tenant_a", "chat") == False
        # tenant_a overrides blog to true
        assert manager.is_module_enabled("tenant_a", "blog") == True
    
    def test_is_module_enabled_nonexistent_module(self, config_file):
        """Test checking non-existent module."""
        manager = TenantConfigManager(config_file)
        
        # Module not configured anywhere should be False
        assert manager.is_module_enabled("tenant_a", "nonexistent") == False
    
    def test_get_enabled_modules(self, config_file):
        """Test getting set of enabled modules."""
        manager = TenantConfigManager(config_file)
        
        # Tenant A has chat=false and blog=true (+ inherited tickets=false, invoices=false)
        enabled = manager.get_enabled_modules("tenant_a")
        assert "blog" in enabled
        assert "chat" not in enabled
        assert "tickets" not in enabled
        assert "invoices" not in enabled
    
    def test_get_all_modules(self, config_file):
        """Test getting all modules defined in config."""
        manager = TenantConfigManager(config_file)
        
        all_modules = manager.get_all_modules()
        assert "chat" in all_modules
        assert "blog" in all_modules
        assert "tickets" in all_modules
        assert "invoices" in all_modules
    
    def test_invalid_json_file(self):
        """Test handling of invalid JSON."""
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, 'w') as f:
                f.write("{ invalid json }")
            
            manager = TenantConfigManager(path)
            # Should fall back to empty config
            assert manager._config == {"defaults": {"modules": {}}, "tenants": {}}
        finally:
            os.unlink(path)
    
    def test_reload_config(self, config_file):
        """Test reloading configuration."""
        manager = TenantConfigManager(config_file)
        
        # Verify initial state
        assert manager.is_module_enabled("tenant_a", "chat") == False
        
        # Modify the config file
        with open(config_file, 'r') as f:
            config = json.load(f)
        config["tenants"]["tenant_a"]["modules"]["chat"] = True
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        # Reload and verify new state
        manager.reload()
        assert manager.is_module_enabled("tenant_a", "chat") == True
    
    def test_get_config_value(self, config_file):
        """Test getting arbitrary config values."""
        manager = TenantConfigManager(config_file)
        
        # Get existing value
        modules = manager.get_config_value("tenant_a", "modules")
        assert modules is not None
        
        # Get non-existent value with default
        value = manager.get_config_value("tenant_a", "nonexistent", default="fallback")
        assert value == "fallback"


class TestConvenienceFunctions:
    """Tests for convenience wrapper functions."""
    
    @pytest.fixture
    def setup_global_manager(self):
        """Setup global config manager for testing."""
        config = {
            "defaults": {
                "modules": {"test_module": True}
            },
            "tenants": {
                "test_tenant": {
                    "modules": {"test_module": False}
                }
            }
        }
        
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(config, f)
            
            # Reset global manager
            import tenant_config
            tenant_config._manager = TenantConfigManager(path)
            yield path
        finally:
            os.unlink(path)
            # Reset global manager
            import tenant_config
            tenant_config._manager = None
    
    def test_is_module_enabled_convenience(self, setup_global_manager):
        """Test convenience function for module checking."""
        assert is_module_enabled("default", "test_module") == True
        assert is_module_enabled("test_tenant", "test_module") == False
    
    def test_get_tenant_config_convenience(self, setup_global_manager):
        """Test convenience function for config retrieval."""
        config = get_tenant_config("test_tenant")
        assert "modules" in config
        assert config["modules"]["test_module"] == False
    
    def test_get_enabled_modules_convenience(self, setup_global_manager):
        """Test convenience function for enabled modules."""
        enabled = get_enabled_modules("default")
        assert "test_module" in enabled


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_tenant_id(self):
        """Test handling empty tenant ID."""
        config = TenantConfigManager("/nonexistent/path/tenants.json")
        result = config.get_tenant_config("")
        # Should get defaults
        assert "modules" in result
    
    def test_none_tenant_id(self):
        """Test handling None tenant ID."""
        config = TenantConfigManager("/nonexistent/path/tenants.json")
        result = config.get_tenant_config(None)
        # Should get defaults
        assert "modules" in result
    
    def test_module_as_dict(self):
        """Test module configuration as dict with 'enabled' key."""
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            config = {
                "defaults": {
                    "modules": {
                        "advanced_module": {"enabled": True, "tier": "premium"}
                    }
                }
            }
            with os.fdopen(fd, 'w') as f:
                json.dump(config, f)
            
            manager = TenantConfigManager(path)
            assert manager.is_module_enabled("default", "advanced_module") == True
        finally:
            os.unlink(path)
    
    def test_invalid_module_value(self):
        """Test handling invalid module values."""
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            config = {
                "defaults": {
                    "modules": {
                        "bad_module": "yes",  # Should be boolean
                        "another_bad": None,
                    }
                }
            }
            with os.fdopen(fd, 'w') as f:
                json.dump(config, f)
            
            manager = TenantConfigManager(path)
            # Should treat non-boolean as False (safe)
            assert manager.is_module_enabled("default", "bad_module") == False
            assert manager.is_module_enabled("default", "another_bad") == False
        finally:
            os.unlink(path)


# Integration tests would go here, possibly with Flask test client
# These are more complex and depend on Flask app setup


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
