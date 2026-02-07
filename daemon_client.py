#!/usr/bin/env python3
"""
Simply Plural Daemon Client

Client library for connecting to the Simply Plural daemon via Unix domain socket.
Provides high-level methods for querying daemon state.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any

from daemon_protocol import (
    Request,
    Response,
    CommandType,
    ResponseStatus,
)


class DaemonClient:
    """
    Client for connecting to Simply Plural daemon
    
    Provides methods to communicate with the daemon over Unix socket
    """
    
    def __init__(self, profile: str = "default", timeout: float = 5.0):
        """
        Initialize daemon client
        
        Args:
            profile: Profile name (determines socket path)
            timeout: Request timeout in seconds
        """
        self.profile = profile
        self.timeout = timeout
        self.socket_path = f"/tmp/sp-daemon-{profile}.sock"
    
    def is_running(self) -> bool:
        """
        Check if daemon is running
        
        Returns:
            True if daemon socket exists and is accessible
        """
        return os.path.exists(self.socket_path)
    
    async def send_request(self, request: Request) -> Response:
        """
        Send a request to the daemon
        
        Args:
            request: Request object
            
        Returns:
            Response object
            
        Raises:
            ConnectionError: If cannot connect to daemon
            TimeoutError: If request times out
        """
        if not self.is_running():
            raise ConnectionError(f"Daemon not running (socket not found: {self.socket_path})")
        
        try:
            # Connect to Unix socket
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(self.socket_path),
                timeout=self.timeout
            )
            
            # Send request
            request_json = request.to_json()
            writer.write(request_json.encode('utf-8'))
            await writer.drain()
            
            # Read response
            response_data = await asyncio.wait_for(
                reader.read(1024 * 1024),  # 1MB max
                timeout=self.timeout
            )
            
            # Close connection
            writer.close()
            await writer.wait_closed()
            
            # Parse response
            response_json = response_data.decode('utf-8')
            response_dict = json.loads(response_json)
            response = Response.from_dict(response_dict)
            
            return response
            
        except asyncio.TimeoutError:
            raise TimeoutError(f"Request to daemon timed out after {self.timeout}s")
        except Exception as e:
            raise ConnectionError(f"Error communicating with daemon: {e}")
    
    async def ping(self) -> bool:
        """
        Ping the daemon
        
        Returns:
            True if daemon responds successfully
        """
        request = Request.create(CommandType.PING)
        response = await self.send_request(request)
        
        return response.status == ResponseStatus.OK
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Get daemon status
        
        Returns:
            Dictionary with daemon status information
        """
        request = Request.create(CommandType.STATUS)
        response = await self.send_request(request)
        
        if response.status == ResponseStatus.OK:
            return response.data
        else:
            raise RuntimeError(f"Status request failed: {response.error}")
    
    async def get_fronters(self) -> Dict[str, Any]:
        """
        Get current fronters
        
        Returns:
            Dictionary with fronters data
        """
        request = Request.create(CommandType.FRONTING)
        response = await self.send_request(request)
        
        if response.status == ResponseStatus.OK:
            return response.data
        else:
            raise RuntimeError(f"Fronters request failed: {response.error}")
    
    async def get_members(self) -> Dict[str, Any]:
        """
        Get all members
        
        Returns:
            Dictionary with members data
        """
        request = Request.create(CommandType.MEMBERS)
        response = await self.send_request(request)
        
        if response.status == ResponseStatus.OK:
            return response.data
        else:
            raise RuntimeError(f"Members request failed: {response.error}")
    
    async def get_custom_fronts(self) -> Dict[str, Any]:
        """
        Get all custom fronts
        
        Returns:
            Dictionary with custom fronts data
        """
        request = Request.create(CommandType.CUSTOM_FRONTS)
        response = await self.send_request(request)
        
        if response.status == ResponseStatus.OK:
            return response.data
        else:
            raise RuntimeError(f"Custom fronts request failed: {response.error}")
    
    async def switch(self, entity_names: list) -> Dict[str, Any]:
        """
        Register a switch
        
        Args:
            entity_names: List of member/custom front names
            
        Returns:
            Dictionary with switch result
        """
        request = Request.create(
            CommandType.SWITCH,
            args={'entities': entity_names}
        )
        response = await self.send_request(request)
        
        if response.status == ResponseStatus.OK:
            return response.data
        else:
            raise RuntimeError(f"Switch request failed: {response.error}")
    
    async def reload(self) -> bool:
        """
        Reload daemon configuration
        
        Returns:
            True if reload successful
        """
        request = Request.create(CommandType.RELOAD)
        response = await self.send_request(request)
        
        return response.status == ResponseStatus.OK


# Synchronous wrapper for convenience
class DaemonClientSync:
    """
    Synchronous wrapper for DaemonClient
    
    Provides synchronous methods by running async operations in event loop
    """
    
    def __init__(self, profile: str = "default", timeout: float = 5.0):
        self.client = DaemonClient(profile, timeout)
    
    def _run(self, coro):
        """Run async coroutine in event loop"""
        try:
            loop = asyncio.get_running_loop()
            # Already in event loop, create task
            return asyncio.create_task(coro)
        except RuntimeError:
            # No event loop, create new one
            return asyncio.run(coro)
    
    def is_running(self) -> bool:
        """Check if daemon is running"""
        return self.client.is_running()
    
    def ping(self) -> bool:
        """Ping the daemon"""
        return self._run(self.client.ping())
    
    def get_status(self) -> Dict[str, Any]:
        """Get daemon status"""
        return self._run(self.client.get_status())
    
    def get_fronters(self) -> Dict[str, Any]:
        """Get current fronters"""
        return self._run(self.client.get_fronters())
    
    def get_members(self) -> Dict[str, Any]:
        """Get all members"""
        return self._run(self.client.get_members())
    
    def get_custom_fronts(self) -> Dict[str, Any]:
        """Get all custom fronts"""
        return self._run(self.client.get_custom_fronts())
    
    def switch(self, entity_names: list) -> Dict[str, Any]:
        """Register a switch"""
        return self._run(self.client.switch(entity_names))
    
    def reload(self) -> bool:
        """Reload daemon configuration"""
        return self._run(self.client.reload())


# CLI test function
async def main():
    """Test daemon client from command line"""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Test daemon client")
    parser.add_argument('--profile', default='default', help='Profile name')
    parser.add_argument('command', choices=['ping', 'status', 'fronting', 'members', 'custom-fronts'])
    args = parser.parse_args()
    
    client = DaemonClient(args.profile)
    
    if not client.is_running():
        print(f"Error: Daemon not running (profile: {args.profile})")
        print(f"Socket not found: {client.socket_path}")
        sys.exit(1)
    
    try:
        if args.command == 'ping':
            result = await client.ping()
            print(f"Ping: {'✓ OK' if result else '✗ FAILED'}")
        
        elif args.command == 'status':
            status = await client.get_status()
            print("Daemon Status:")
            print(json.dumps(status, indent=2))
        
        elif args.command == 'fronting':
            fronters = await client.get_fronters()
            print("Current Fronters:")
            print(json.dumps(fronters, indent=2))
        
        elif args.command == 'members':
            members = await client.get_members()
            print("Members:")
            print(json.dumps(members, indent=2))
        
        elif args.command == 'custom-fronts':
            custom_fronts = await client.get_custom_fronts()
            print("Custom Fronts:")
            print(json.dumps(custom_fronts, indent=2))
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
