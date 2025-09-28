"""
Simply Plural API Client

Handles all communication with the Simply Plural API, including:
- Authentication
- Rate limiting
- Error handling
- Endpoint abstraction
"""

import requests
import time
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path


class APIError(Exception):
    """Exception raised for API-related errors"""
    pass


class SimplyPluralAPI:
    """Simply Plural API client"""
    
    BASE_URL = "https://api.apparyllis.com/v1"
    
    def __init__(self, api_token: str, config_manager=None, debug: bool = False, cache_manager=None):
        self.api_token = api_token
        self.config = config_manager
        self.debug = debug
        self.cache = cache_manager
        
        # Get timeout and retry settings from config
        self.timeout = config_manager.api_timeout if config_manager else 10
        self.max_retries = config_manager.max_retries if config_manager else 3
        
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': api_token,
            'User-Agent': 'SimplePlural-CLI/1.0',
            'Content-Type': 'application/json'
        })
    
    def _filter_sensitive_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Filter out any potentially sensitive headers from debug output"""
        # Headers that should never be logged (case-insensitive)
        sensitive_headers = {'authorization', 'x-api-key', 'x-auth-token', 'bearer'}
        
        filtered = {}
        for key, value in headers.items():
            if key.lower() in sensitive_headers:
                filtered[key] = "[REDACTED]"
            else:
                filtered[key] = value
        return filtered
    
    def _sanitize_debug_data(self, data: Any) -> Any:
        """Remove any potentially sensitive data from debug output"""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if any(sensitive in key.lower() for sensitive in ['token', 'auth', 'password', 'secret']):
                    sanitized[key] = "[REDACTED]"
                else:
                    sanitized[key] = self._sanitize_debug_data(value)
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_debug_data(item) for item in data]
        else:
            return data
    
    def _sanitize_debug_text(self, text: str) -> str:
        """Remove tokens from debug text output"""
        # Simple pattern to catch base64-like tokens (44+ chars of base64)
        import re
        # Replace what looks like long base64 tokens with [REDACTED]
        sanitized = re.sub(r'[A-Za-z0-9+/]{44,}={0,2}', '[REDACTED_TOKEN]', text)
        return sanitized
    
    def _generate_fallback_name(self, member_id: str, fronter: Dict[str, Any]) -> str:
        """Generate a more useful fallback name when member details aren't available"""
        # Extract potentially useful info from the fronter object
        custom_status = fronter.get('content', {}).get('customStatus', '')
        
        # Use middle section of ID for better uniqueness (where IDs actually differ)
        if len(member_id) >= 16:
            # Show chars 8-16 which tend to be more unique
            unique_part = member_id[8:16]
            short_id = f"ID-{unique_part}"
        elif len(member_id) >= 8:
            # Fallback to first 8 chars
            short_id = f"ID-{member_id[:8]}"
        else:
            short_id = f"ID-{member_id}"
        
        # If there's a custom status, include it
        if custom_status and custom_status.strip():
            return f"{short_id} ({custom_status.strip()})"
        else:
            return short_id
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[Any, Any]:
        """Make an API request with retries"""
        
        url = f"{self.BASE_URL}{endpoint}"
        # Use configured timeout, allow override via kwargs
        timeout = kwargs.pop('timeout', self.timeout)
        
        if self.debug:
            print(f"DEBUG: {method} {url}")
            if 'json' in kwargs:
                print(f"DEBUG: Request body: {json.dumps(kwargs['json'], indent=2)}")
            if 'params' in kwargs:
                print(f"DEBUG: Query params: {kwargs['params']}")
        
        last_exception = None
        
        # Retry loop
        for attempt in range(self.max_retries):
            try:
                response = self.session.request(method, url, timeout=timeout, **kwargs)
                
                if self.debug:
                    print(f"DEBUG: Response status: {response.status_code}")
                    # Safely show response headers (never contains our auth token)
                    safe_headers = self._filter_sensitive_headers(dict(response.headers))
                    print(f"DEBUG: Response headers: {safe_headers}")
                    # Sanitize response text to prevent token leaks
                    sanitized_response = self._sanitize_debug_text(response.text)
                    print(f"DEBUG: Response text: {sanitized_response[:500]}{'...' if len(sanitized_response) > 500 else ''}")
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    if self.debug:
                        print(f"DEBUG: Server returned HTTP 429 - actual rate limit from API")
                    raise APIError(f"Rate limited (server). Retry after {retry_after} seconds.")
                
                # Handle other HTTP errors
                if response.status_code == 401:
                    raise APIError("HTTP 401 - Bad Request. Check if your token has the correct permissions (in particular, write permissions are needed to update fronters). If you are sure your token is not the problem, open a bug report at https://github.com/SiteRelEnby/simplyplural-cli/issues")
                elif response.status_code == 403:
                    if self.debug:
                        print(f"DEBUG: HTTP 403 - Access denied. Check your token is entered correctly and not revoked.")
                    raise APIError("HTTP 403 - Access denied. Check your token is entered correctly and not revoked.")
                elif response.status_code == 404:
                    if self.debug:
                        print(f"DEBUG: HTTP 404 - Endpoint {endpoint} not found")
                    raise APIError("HTTP 404 - Not found. This is probably a bug - open a report at https://github.com/SiteRelEnby/simplyplural-cli/issues")
                elif response.status_code >= 400:
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('message', f'HTTP {response.status_code}')
                    except:
                        error_msg = f'HTTP {response.status_code}: {response.text[:100]}'
                    if self.debug:
                        sanitized_error = self._sanitize_debug_text(error_msg)
                        print(f"DEBUG: HTTP {response.status_code} error: {sanitized_error}")
                    raise APIError(error_msg)
                
                # Parse JSON response
                try:
                    # Handle empty successful responses (like PATCH updates)
                    if response.status_code == 200 and not response.text.strip():
                        return {}
                        
                    result = response.json()
                    if self.debug:
                        print(f"DEBUG: Parsed JSON: {json.dumps(self._sanitize_debug_data(result), indent=2) if result else 'None'}")
                    return result
                except json.JSONDecodeError:
                    if response.status_code == 204:  # No Content
                        return {}
                    # For successful responses with empty content, return empty dict
                    if response.status_code == 200 and not response.text.strip():
                        return {}
                    raise APIError("Invalid JSON response from API")
                    
            except (requests.Timeout, requests.ConnectionError, requests.RequestException) as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    if self.debug:
                        print(f"DEBUG: Request failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                    # Exponential backoff for retries
                    time.sleep(2 ** attempt)
                    continue
                else:
                    # Final attempt failed
                    if isinstance(e, requests.Timeout):
                        raise APIError("Request timed out. Check your connection.")
                    elif isinstance(e, requests.ConnectionError):
                        raise APIError("Connection failed. Check your internet connection.")
                    else:
                        raise APIError(f"Request failed: {e}")
        
        # This shouldn't be reached, but just in case
        raise APIError(f"Request failed after {self.max_retries} attempts: {last_exception}")
    
    def get_fronters(self) -> Dict[str, Any]:
        """Get current fronters with resolved member/custom front names"""
        fronters_response = self._request('GET', '/fronters')
        
        # If it's a list of fronter objects, try to resolve names
        if isinstance(fronters_response, list):
            resolved_fronters = []
            for fronter in fronters_response:
                if 'content' in fronter and 'member' in fronter['content']:
                    entity_id = fronter['content']['member']
                    is_custom = fronter['content'].get('custom', False)
                    
                    try:
                        if is_custom:
                            # It's a custom front
                            custom_front = self.get_custom_front(entity_id)
                            fronter_with_name = fronter.copy()
                            fronter_with_name['name'] = custom_front.get('content', {}).get('name', self._generate_fallback_name(entity_id, fronter))
                            fronter_with_name['type'] = 'custom_front'
                        else:
                            # It's a regular member
                            member = self.get_member(entity_id)
                            fronter_with_name = fronter.copy()
                            fronter_with_name['name'] = member.get('content', {}).get('name', self._generate_fallback_name(entity_id, fronter))
                            fronter_with_name['type'] = 'member'
                        
                        resolved_fronters.append(fronter_with_name)
                    except APIError:
                        # If we can't get details, use ID as fallback
                        fronter_with_name = fronter.copy()
                        fronter_with_name['name'] = self._generate_fallback_name(entity_id, fronter)
                        fronter_with_name['type'] = 'custom_front' if is_custom else 'member'
                        resolved_fronters.append(fronter_with_name)
                else:
                    resolved_fronters.append(fronter)
            return resolved_fronters
        
        return fronters_response
    
    def get_system_id(self) -> str:
        """Get the system ID from /me endpoint"""
        # Check if we have it cached
        if hasattr(self, '_system_id') and self._system_id:
            return self._system_id
            
        try:
            response = self._request('GET', '/me')
            # The system ID might be in different fields
            system_id = None
            
            if isinstance(response, dict):
                # Try common field names for system ID
                for field in ['id', 'uid', 'system_id', 'systemId', 'user_id', 'userId']:
                    if field in response and response[field]:
                        system_id = response[field]
                        break
                        
                # Also check if it's nested
                if not system_id and 'content' in response:
                    content = response['content']
                    for field in ['id', 'uid', 'system_id', 'systemId']:
                        if field in content and content[field]:
                            system_id = content[field]
                            break
            
            if not system_id:
                if self.debug:
                    print(f"DEBUG: Could not find system ID in /me response: {response}")
                raise APIError("Could not extract system ID from /me endpoint")
            
            # Cache it
            self._system_id = system_id
            if self.debug:
                print(f"DEBUG: Found system ID: {system_id}")
                
            return system_id
            
        except APIError as e:
            if self.debug:
                print(f"DEBUG: Failed to get system ID from /me: {e}")
            raise APIError(f"Could not get system ID: {e}")
    
    def get_members(self) -> List[Dict[str, Any]]:
        """Get all members using the correct /members/{system_id} format"""
        try:
            # Get system ID first  
            system_id = self.get_system_id()
            
            # Try the correct endpoint format
            endpoint = f'/members/{system_id}'
            
            if self.debug:
                print(f"DEBUG: Trying members endpoint {endpoint}")
                
            response = self._request('GET', endpoint)
            
            # Handle different response formats
            if isinstance(response, list):
                return response
            elif isinstance(response, dict):
                # Try common keys for member lists
                for key in ['members', 'profiles', 'system', 'data']:
                    if key in response and isinstance(response[key], list):
                        return response[key]
                        
                # If it's a single member object, wrap in list
                if 'id' in response:
                    return [response]
                    
            if self.debug:
                print(f"DEBUG: Unexpected response format from {endpoint}: {type(response)}")
                print(f"DEBUG: Response: {response}")
                
            # If we got here, try fallback endpoints
            if self.debug:
                print(f"DEBUG: Trying fallback endpoints...")
                
            fallback_endpoints = [
                '/members',           # Maybe it works without system ID
                '/profiles',          # Maybe it's called profiles
                '/system',            # Maybe system info includes members
                f'/system/{system_id}/members',  # Alternative format
                f'/user/{system_id}/members',    # User-scoped format
            ]
            
            for fallback_endpoint in fallback_endpoints:
                try:
                    if self.debug:
                        print(f"DEBUG: Trying fallback endpoint {fallback_endpoint}")
                    response = self._request('GET', fallback_endpoint)
                    
                    if isinstance(response, list):
                        return response
                    elif isinstance(response, dict):
                        for key in ['members', 'profiles', 'system', 'data']:
                            if key in response and isinstance(response[key], list):
                                return response[key]
                                
                except APIError as e:
                    if self.debug:
                        print(f"DEBUG: Fallback endpoint {fallback_endpoint} failed: {e}")
                    continue
            
            raise APIError(f"No valid members endpoint found. Tried {endpoint} and fallbacks.")
            
        except APIError as e:
            if "Could not get system ID" in str(e):
                # If we can't get system ID, the user might need to check their token permissions
                raise APIError(f"Cannot get member list: {e}. Check if your API token has the required permissions.")
            else:
                raise e
    
    def get_member(self, member_id: str) -> Dict[str, Any]:
        """Get a specific member with caching using the correct /member/{system_id}/{member_id} format"""
        # Check cache first
        if self.cache:
            cached_member = self.cache.get_member(member_id)
            if cached_member:
                if self.debug:
                    print(f"DEBUG: Using cached member {member_id}: {cached_member.get('content', {}).get('name', 'Unknown')}")
                return cached_member
        
        if self.debug:
            print(f"DEBUG: Cache miss for member {member_id}, fetching from API")
        
        try:
            # Get system ID first
            system_id = self.get_system_id()
            
            # Use the correct endpoint format
            endpoint = f'/member/{system_id}/{member_id}'
            
            if self.debug:
                print(f"DEBUG: Trying to get member {member_id} from {endpoint}")
                
            member_data = self._request('GET', endpoint)
            
            # Cache the result
            if self.cache:
                self.cache.set_member(member_id, member_data)
                if self.debug:
                    print(f"DEBUG: Cached member {member_id}: {member_data.get('content', {}).get('name', 'Unknown')}")
            
            return member_data
            
        except APIError as e:
            if self.debug:
                print(f"DEBUG: Failed to get member {member_id}: {e}")
            raise APIError(f"Could not fetch member {member_id}: {e}")
    
    def get_custom_fronts(self) -> List[Dict[str, Any]]:
        """Get all custom fronts for this system"""
        # Try cache first
        if self.cache:
            cached_custom_fronts = self.cache.get_custom_fronts()
            if cached_custom_fronts is not None:
                if self.debug:
                    print(f"DEBUG: Using cached custom fronts: {len(cached_custom_fronts)} custom fronts")
                return cached_custom_fronts
        
        try:
            system_id = self.get_system_id()
            if self.debug:
                print(f"DEBUG: Fetching custom fronts for system {system_id}")
            
            response = self._request('GET', f'/customFronts/{system_id}')
            
            # Return the list of custom fronts
            custom_fronts = response if isinstance(response, list) else []
            
            # Cache the results
            if self.cache:
                self.cache.set_custom_fronts(custom_fronts)
            
            return custom_fronts
            
        except APIError as e:
            if self.debug:
                print(f"DEBUG: Failed to get custom fronts: {e}")
            raise APIError(f"Could not fetch custom fronts: {e}")
    
    def get_custom_front(self, custom_front_id: str) -> Dict[str, Any]:
        """Get a specific custom front by ID"""
        # Try cache first
        if self.cache:
            cached_custom_front = self.cache.get_custom_front(custom_front_id)
            if cached_custom_front is not None:
                if self.debug:
                    print(f"DEBUG: Using cached custom front {custom_front_id}")
                return cached_custom_front
        
        try:
            system_id = self.get_system_id()
            if self.debug:
                print(f"DEBUG: Fetching custom front {custom_front_id} for system {system_id}")
            
            response = self._request('GET', f'/customFront/{system_id}/{custom_front_id}')
            
            if 'content' in response:
                # Cache the result
                if self.cache:
                    self.cache.set_custom_front(custom_front_id, response)
                return response
            else:
                raise APIError(f"Invalid custom front response format")
            
        except APIError as e:
            if self.debug:
                print(f"DEBUG: Failed to get custom front {custom_front_id}: {e}")
            raise APIError(f"Could not fetch custom front {custom_front_id}: {e}")

    def register_switch(self, names: List[str], note: Optional[str] = None) -> Dict[str, Any]:
        """Register a switch to one or more members or custom fronts using the frontHistory API"""
        
        # Get both members and custom fronts
        members = self.get_members()
        custom_fronts = self.get_custom_fronts()
        
        # Create maps for name lookup
        member_map = {m['content']['name'].lower(): {'id': m['id'], 'type': 'member'} for m in members}
        custom_front_map = {cf['content']['name'].lower(): {'id': cf['id'], 'type': 'custom_front'} for cf in custom_fronts}
        
        # Combine both maps for unified lookup
        entity_map = {**member_map, **custom_front_map}
        
        entities = []
        for name in names:
            entity = entity_map.get(name.lower())
            if not entity:
                # Try partial matching in both members and custom fronts
                member_matches = [m for m in members if name.lower() in m['content']['name'].lower()]
                custom_front_matches = [cf for cf in custom_fronts if name.lower() in cf['content']['name'].lower()]
                
                all_matches = [
                    {'entity': m, 'type': 'member'} for m in member_matches
                ] + [
                    {'entity': cf, 'type': 'custom_front'} for cf in custom_front_matches
                ]
                
                if len(all_matches) == 1:
                    match = all_matches[0]
                    entity = {'id': match['entity']['id'], 'type': match['type']}
                elif len(all_matches) > 1:
                    names_list = [f"{match['entity']['content']['name']} ({match['type']})" for match in all_matches]
                    raise APIError(f"Ambiguous name '{name}'. Matches: {', '.join(names_list)}")
                else:
                    available_members = [m['content']['name'] for m in members]
                    available_custom_fronts = [cf['content']['name'] for cf in custom_fronts]
                    all_available = [f"{name} (member)" for name in available_members] + [f"{name} (custom_front)" for name in available_custom_fronts]
                    raise APIError(f"Name '{name}' not found. Available: {', '.join(all_available)}")
            entities.append(entity)
        
        # Step 1: End all current live fronting sessions
        current_fronters = self._request('GET', '/fronters')
        current_time_ms = int(time.time() * 1000)
        
        if self.debug:
            print(f"DEBUG: Found {len(current_fronters)} current fronters to end")
        
        for fronter in current_fronters:
            if fronter.get('content', {}).get('live', False):
                front_id = fronter['id']
                if self.debug:
                    print(f"DEBUG: Ending front session {front_id}")
                
                end_data = {
                    'live': False,
                    'endTime': current_time_ms
                }
                
                try:
                    self._request('PATCH', f'/frontHistory/{front_id}', json=end_data)
                except APIError as e:
                    if self.debug:
                        print(f"DEBUG: Warning - failed to end front session {front_id}: {e}")
                    # Continue anyway - maybe it was already ended
        
        # Step 2: Create new front sessions for the requested entities (members or custom fronts)
        import random
        results = []
        
        for entity in entities:
            # Generate a new ObjectId-style string (24 hex characters)
            new_front_id = ''.join(random.choices('0123456789abcdef', k=24))
            
            start_data = {
                'member': entity['id'],
                'startTime': current_time_ms + 1,  # Slightly after end time
                'live': True,
                'custom': entity['type'] == 'custom_front'
            }
            
            if note:
                start_data['customStatus'] = note
            
            if self.debug:
                entity_type = 'custom front' if entity['type'] == 'custom_front' else 'member'
                print(f"DEBUG: Creating front session {new_front_id} for {entity_type} {entity['id']}")
                
            result = self._request('POST', f'/frontHistory/{new_front_id}', json=start_data)
            results.append(result)
        
        return results[0] if len(results) == 1 else results
    
    def get_switches(self, period: str = "recent", count: int = 10) -> List[Dict[str, Any]]:
        """Get switch history using the correct frontHistory endpoint with required time parameters"""
        try:
            # Get system ID first
            system_id = self.get_system_id()
            
            # Calculate time range based on period
            current_time_ms = int(time.time() * 1000)
            
            if period == "today":
                # Start of today
                today = time.gmtime(time.time())
                start_of_day = time.mktime((today.tm_year, today.tm_mon, today.tm_mday, 0, 0, 0, 0, 0, 0))
                start_time_ms = int(start_of_day * 1000)
            elif period == "week":
                # Start of this week (7 days ago)
                start_time_ms = current_time_ms - (7 * 24 * 60 * 60 * 1000)
            else:  # "recent" or any other value
                # Default to last 30 days
                start_time_ms = current_time_ms - (30 * 24 * 60 * 60 * 1000)
            
            # Use the correct frontHistory endpoint with required parameters
            endpoint = f'/frontHistory/{system_id}'
            params = {
                'startTime': start_time_ms,
                'endTime': current_time_ms
            }
            
            if self.debug:
                print(f"DEBUG: Using frontHistory endpoint: {endpoint}")
                print(f"DEBUG: Time range: {start_time_ms} to {current_time_ms} ({period})")
                
            response = self._request('GET', endpoint, params=params)
            
            # Handle the response - it should be a list of front history entries
            if isinstance(response, list):
                # Sort by timestamp (most recent first) and limit count
                sorted_entries = sorted(response, 
                                       key=lambda x: x.get('content', {}).get('startTime', 0), 
                                       reverse=True)
                return sorted_entries[:count]
            else:
                if self.debug:
                    print(f"DEBUG: Unexpected frontHistory response format: {type(response)}")
                return []
                
        except APIError as e:
            if self.debug:
                print(f"DEBUG: Failed to get switch history: {e}")
            raise APIError(f"Could not fetch switch history: {e}")
    
    def export_data(self) -> Dict[str, Any]:
        """Export all user data"""
        data = {}
        
        try:
            data['members'] = self.get_members()
        except APIError:
            data['members'] = []
        
        try:
            data['fronters'] = self.get_fronters()
        except APIError:
            data['fronters'] = {}
        
        try:
            data['switches'] = self.get_switches(count=1000)
        except APIError:
            data['switches'] = []
        
        data['exported_at'] = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
        return data
