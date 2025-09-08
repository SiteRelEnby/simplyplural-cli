#!/usr/bin/env python3
"""
Test script for Simply Plural CLI

Run this to verify that all modules import correctly and basic functionality works.
"""

import sys
import os
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    
    try:
        from api_client import SimplyPluralAPI, APIError
        print("[OK] api_client imports successfully")
    except ImportError as e:
        print(f"[FAIL] api_client import failed: {e}")
        return False
    
    try:
        from cache_manager import CacheManager, CacheEntry
        print("[OK] cache_manager imports successfully")
    except ImportError as e:
        print(f"[FAIL] cache_manager import failed: {e}")
        return False
    
    try:
        from config_manager import ConfigManager
        print("[OK] config_manager imports successfully")
    except ImportError as e:
        print(f"[FAIL] config_manager import failed: {e}")
        return False
    
    return True

def test_config_manager():
    """Test basic config manager functionality"""
    print("\nTesting config manager...")
    
    try:
        from config_manager import ConfigManager
        
        # Create temp config manager (won't interfere with real config)
        config = ConfigManager()
        
        # Test default values
        assert config.cache_duration == 300
        assert config.output_format == 'human'
        assert config.api_token is None
        
        print("[OK] Config manager basic functionality works")
        print(f"  Config dir: {config.config_dir}")
        print(f"  Cache dir: {config.cache_dir}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Config manager test failed: {e}")
        return False

def test_cache_manager():
    """Test basic cache manager functionality"""
    print("\nTesting cache manager...")
    
    try:
        from cache_manager import CacheManager
        from config_manager import ConfigManager
        
        config = ConfigManager()
        cache = CacheManager(config.cache_dir)
        
        # Test basic set/get
        test_data = {"test": "data", "timestamp": "2024-01-01"}
        cache.set("test_key", test_data)
        
        retrieved = cache.get("test_key")
        assert retrieved == test_data
        
        print("[OK] Cache manager basic functionality works")
        return True
        
    except Exception as e:
        print(f"[FAIL] Cache manager test failed: {e}")
        return False

def test_cli_help():
    """Test that the main CLI script can show help"""
    print("\nTesting CLI help...")
    
    try:
        # Import the main CLI module
        import sp
        
        # Test that help can be generated (this tests argument parsing)
        import subprocess
        result = subprocess.run([sys.executable, "sp.py", "--help"], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and "Simply Plural CLI" in result.stdout:
            print("[OK] CLI help works")
            return True
        else:
            print(f"[FAIL] CLI help failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"[FAIL] CLI help test failed: {e}")
        return False

def test_dependencies():
    """Test that required dependencies are available"""
    print("\nTesting dependencies...")
    
    try:
        import requests
        print(f"[OK] requests library available (version {requests.__version__})")
    except ImportError:
        print("[FAIL] requests library not found - run: pip install requests")
        return False
    
    try:
        import json
        print("[OK] json module available")
    except ImportError:
        print("[FAIL] json module not found")
        return False
    
    return True

def main():
    """Run all tests"""
    print("Simply Plural CLI Test Suite")
    print("=" * 40)
    
    tests = [
        test_dependencies,
        test_imports,
        test_config_manager,
        test_cache_manager,
        test_cli_help
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"[FAIL] Test {test.__name__} crashed: {e}")
    
    print("\n" + "=" * 40)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("All tests passed! The CLI should work correctly.")
        print("\nNext steps:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Set up the CLI: python sp.py config --setup")
        print("3. Test basic functionality: python sp.py --help")
    else:
        print("Some tests failed. Check the output above for issues.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
