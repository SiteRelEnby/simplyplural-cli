"""
Cache Manager for Simply Plural CLI

Handles local caching of API responses to improve performance and reduce API calls.
Uses both memory and file-based caching with configurable TTL.
"""

import json
import time
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class CacheEntry:
    """Represents a cached item with metadata"""
    data: Any
    timestamp: float
    ttl: int  # Time to live in seconds
    
    @property
    def is_expired(self) -> bool:
        """Check if this cache entry has expired"""
        return (time.time() - self.timestamp) > self.ttl
    
    @property
    def age(self) -> int:
        """Get age of cache entry in seconds"""
        return int(time.time() - self.timestamp)


class CacheManager:
    """Manages local caching for API responses"""
    
    def __init__(self, cache_dir: Path, config_manager=None):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.config = config_manager
        
        # In-memory cache for very recent data
        self.memory_cache: Dict[str, CacheEntry] = {}
        
        # Default TTL values (in seconds) - use config if available
        if self.config:
            self.default_ttl = {
                'fronters': self.config.cache_fronters_ttl,
                'members': self.config.cache_members_ttl,
                'switches': self.config.cache_switches_ttl,
                'custom_fronts': self.config.cache_custom_fronts_ttl,
            }
        else:
            self.default_ttl = {
                'fronters': 300,    # 5 minutes
                'members': 3600,    # 1 hour
                'switches': 1800,   # 30 minutes
                'custom_fronts': 3600,  # 1 hour
            }
        
        # Memory cache TTL (shorter for responsiveness)
        self.memory_ttl = {
            'fronters': 300,    # 5 minutes - matches file cache for efficiency
            'members': 300,     # 5 minutes
            'switches': 300,    # 5 minutes
            'custom_fronts': 300,  # 5 minutes
        }
    
    def _get_cache_file(self, key: str) -> Path:
        """Get the cache file path for a given key"""
        return self.cache_dir / f"{key}.json"
    
    def _load_from_file(self, key: str) -> Optional[CacheEntry]:
        """Load cache entry from file"""
        cache_file = self._get_cache_file(key)
        
        try:
            if not cache_file.exists():
                return None
                
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            return CacheEntry(
                data=cache_data['data'],
                timestamp=cache_data['timestamp'],
                ttl=cache_data.get('ttl', self.default_ttl.get(key, 3600))
            )
            
        except (json.JSONDecodeError, KeyError, IOError):
            # If cache file is corrupted, remove it
            try:
                cache_file.unlink()
            except:
                pass
            return None
    
    def _save_to_file(self, key: str, entry: CacheEntry):
        """Save cache entry to file atomically"""
        cache_file = self._get_cache_file(key)
        
        cache_data = {
            'data': entry.data,
            'timestamp': entry.timestamp,
            'ttl': entry.ttl
        }
        
        try:
            # Atomic write using temporary file
            with tempfile.NamedTemporaryFile(
                mode='w', 
                dir=self.cache_dir, 
                delete=False,
                suffix='.tmp'
            ) as tmp_file:
                json.dump(cache_data, tmp_file, indent=2)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
                temp_path = tmp_file.name
            
            # Replace the original file
            os.replace(temp_path, cache_file)
            
        except (IOError, OSError):
            # Clean up temporary file if it exists
            try:
                if 'temp_path' in locals():
                    os.unlink(temp_path)
            except:
                pass
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached data for a key"""
        
        # 1. Check memory cache first (fastest)
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            if not entry.is_expired:
                return entry.data
            else:
                # Remove expired entry
                del self.memory_cache[key]
        
        # 2. Check file cache
        entry = self._load_from_file(key)
        if entry and not entry.is_expired:
            # Promote to memory cache if still fresh enough
            if entry.age <= self.memory_ttl.get(key, 300):
                memory_entry = CacheEntry(
                    data=entry.data,
                    timestamp=time.time(),
                    ttl=self.memory_ttl.get(key, 300)
                )
                self.memory_cache[key] = memory_entry
            
            return entry.data
        
        return None
    
    def set(self, key: str, data: Any, ttl: Optional[int] = None):
        """Set cached data for a key"""
        if ttl is None:
            ttl = self.default_ttl.get(key, 3600)
        
        timestamp = time.time()
        
        # Save to file cache
        file_entry = CacheEntry(data=data, timestamp=timestamp, ttl=ttl)
        self._save_to_file(key, file_entry)
        
        # Save to memory cache with shorter TTL
        memory_ttl = min(ttl, self.memory_ttl.get(key, 300))
        memory_entry = CacheEntry(data=data, timestamp=timestamp, ttl=memory_ttl)
        self.memory_cache[key] = memory_entry
    
    def invalidate(self, key: str):
        """Invalidate cached data for a key"""
        # Remove from memory cache
        if key in self.memory_cache:
            del self.memory_cache[key]
        
        # Remove file cache
        cache_file = self._get_cache_file(key)
        try:
            cache_file.unlink()
        except FileNotFoundError:
            pass
    
    def clear_all(self):
        """Clear all cached data"""
        # Clear memory cache
        self.memory_cache.clear()
        
        # Clear file cache
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
            except:
                pass
    
    def get_cache_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about cached items"""
        info = {}
        
        # Check all possible cache files
        for cache_file in self.cache_dir.glob("*.json"):
            key = cache_file.stem
            entry = self._load_from_file(key)
            
            if entry:
                info[key] = {
                    'age_seconds': entry.age,
                    'ttl_seconds': entry.ttl,
                    'expired': entry.is_expired,
                    'in_memory': key in self.memory_cache,
                    'file_size': cache_file.stat().st_size
                }
        
        return info
    
    # Convenience methods for specific data types
    
    def get_fronters(self) -> Optional[Dict[str, Any]]:
        """Get cached fronters data"""
        return self.get('fronters')
    
    def set_fronters(self, data: Dict[str, Any]):
        """Cache fronters data"""
        self.set('fronters', data)
    
    def invalidate_fronters(self):
        """Invalidate fronters cache (e.g., after a switch)"""
        self.invalidate('fronters')
    
    def get_fronters_timestamp(self) -> Optional[float]:
        """Get timestamp of when fronters were last cached"""
        if 'fronters' in self.memory_cache:
            return self.memory_cache['fronters'].timestamp
        
        entry = self._load_from_file('fronters')
        return entry.timestamp if entry else None
    
    def get_members(self) -> Optional[List[Dict[str, Any]]]:
        """Get cached members data"""
        return self.get('members')
    
    def set_members(self, data: List[Dict[str, Any]]):
        """Cache members data"""
        self.set('members', data)
    
    def get_member(self, member_id: str) -> Optional[Dict[str, Any]]:
        """Get cached individual member data"""
        return self.get(f'member_{member_id}')
    
    def set_member(self, member_id: str, data: Dict[str, Any]):
        """Cache individual member data"""
        self.set(f'member_{member_id}', data)
    
    def get_switches(self, period: str = "recent") -> Optional[List[Dict[str, Any]]]:
        """Get cached switches data"""
        return self.get(f'switches_{period}')
    
    def set_switches(self, data: List[Dict[str, Any]], period: str = "recent"):
        """Cache switches data"""
        self.set(f'switches_{period}', data)
    
    def invalidate_member(self, member_id: str):
        """Invalidate cached member data"""
        self.invalidate(f'member_{member_id}')
    
    def get_custom_fronts(self) -> Optional[List[Dict[str, Any]]]:
        """Get cached custom fronts data"""
        return self.get('custom_fronts')
    
    def set_custom_fronts(self, data: List[Dict[str, Any]]):
        """Cache custom fronts data"""
        self.set('custom_fronts', data)
    
    def get_custom_front(self, custom_front_id: str) -> Optional[Dict[str, Any]]:
        """Get cached individual custom front data"""
        return self.get(f'custom_front_{custom_front_id}')
    
    def set_custom_front(self, custom_front_id: str, data: Dict[str, Any]):
        """Cache individual custom front data"""
        self.set(f'custom_front_{custom_front_id}', data)
    
    def invalidate_custom_front(self, custom_front_id: str):
        """Invalidate cached custom front data"""
        self.invalidate(f'custom_front_{custom_front_id}')
    
    def invalidate_custom_fronts(self):
        """Invalidate all custom fronts cache"""
        self.invalidate('custom_fronts')
