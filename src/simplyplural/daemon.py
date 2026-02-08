#!/usr/bin/env python3
"""
Simply Plural Daemon - WebSocket-based daemon for real-time updates

This daemon maintains a persistent WebSocket connection to the Simply Plural API,
providing real-time updates and instant status queries through a Unix domain socket.
"""

import asyncio
import json
import logging
import sys
import time
import os
from pathlib import Path
from typing import Optional, Dict, Any, Callable
import signal

try:
    import websockets
except ImportError:
    print("Error: websockets library not installed")
    print("Install with: pip3 install websockets>=12.0")
    sys.exit(1)

from .daemon_protocol import (
    WS_ENDPOINT_PROD,
    WS_KEEPALIVE_INTERVAL,
    WS_KEEPALIVE_MESSAGE,
    WS_RECONNECT_INITIAL_DELAY,
    WS_RECONNECT_MAX_DELAY,
    WS_RECONNECT_MULTIPLIER,
    WebSocketOp,
    WSUpdateMessage,
    WSUpdateResult,
    Request,
    Response,
    CommandType,
)


class WebSocketManager:
    """
    Manages WebSocket connection to Simply Plural API
    
    Responsibilities:
    - Connect and authenticate to WebSocket
    - Send keepalive pings every 10 seconds
    - Receive and parse update messages
    - Auto-reconnect on disconnect
    - Notify daemon of updates
    """
    
    def __init__(self, api_token: str, update_callback: Optional[Callable] = None, debug: bool = False):
        """
        Initialize WebSocket manager
        
        Args:
            api_token: Simply Plural API token
            update_callback: Async callback function for updates: (target, operation, obj_id, content)
            debug: Enable debug logging
        """
        self.api_token = api_token
        self.update_callback = update_callback
        self.debug = debug
        
        # Connection state
        self.ws = None
        self.authenticated = False
        self.running = False
        self.reconnect_delay = WS_RECONNECT_INITIAL_DELAY
        
        # Statistics
        self.connect_time = 0.0
        self.last_ping_time = 0.0
        self.last_message_time = 0.0
        self.messages_received = 0
        self.reconnect_count = 0
        
        # Setup logging
        self.logger = logging.getLogger("WebSocketManager")
        if debug:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)
    
    async def connect(self) -> bool:
        """
        Connect to WebSocket and authenticate
        
        Returns:
            True if connection and authentication successful, False otherwise
        """
        try:
            self.logger.info(f"Connecting to {WS_ENDPOINT_PROD}")
            self.ws = await websockets.connect(
                WS_ENDPOINT_PROD,
                ping_interval=None,  # We handle keepalive ourselves
                close_timeout=10
            )
            
            self.connect_time = time.time()
            self.logger.info("WebSocket connected, authenticating...")
            
            # Read initial message (usually empty {})
            try:
                initial_msg = await asyncio.wait_for(self.ws.recv(), timeout=5.0)
                self.logger.debug(f"Initial message: {initial_msg}")
            except asyncio.TimeoutError:
                self.logger.debug("No initial message received")
            
            # Send authentication payload
            auth_payload = {
                'op': WebSocketOp.AUTHENTICATE.value,
                'token': self.api_token
            }
            await self.ws.send(json.dumps(auth_payload))
            
            # Wait for authentication response
            try:
                auth_response = await asyncio.wait_for(self.ws.recv(), timeout=10.0)
                
                # Parse JSON if possible
                try:
                    auth_data = json.loads(auth_response)
                    if auth_data.get('msg') == 'Successfully authenticated':
                        self.authenticated = True
                        self.reconnect_delay = WS_RECONNECT_INITIAL_DELAY  # Reset backoff
                        self.logger.info("✓ Successfully authenticated to WebSocket")
                        return True
                except json.JSONDecodeError:
                    pass
                
                # Check string response
                if "Successfully authenticated" in auth_response:
                    self.authenticated = True
                    self.reconnect_delay = WS_RECONNECT_INITIAL_DELAY  # Reset backoff
                    self.logger.info("✓ Successfully authenticated to WebSocket")
                    return True
                elif "Authentication violation" in auth_response:
                    self.logger.error(f"✗ Authentication failed: {auth_response}")
                    self.authenticated = False
                    return False
                else:
                    self.logger.warning(f"Unexpected auth response: {auth_response}")
                    return False
                    
            except asyncio.TimeoutError:
                self.logger.error("✗ Authentication timeout")
                return False
                
        except Exception as e:
            self.logger.error(f"✗ Connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Gracefully disconnect from WebSocket"""
        if self.ws:
            self.logger.info("Disconnecting from WebSocket")
            await self.ws.close()
            self.ws = None
            self.authenticated = False
    
    async def keepalive_loop(self):
        """
        Send keepalive pings every 10 seconds
        
        Simply Plural expects a "ping" string (not WebSocket ping frames)
        every 10 seconds to keep the connection alive.
        """
        while self.running and self.ws and self.authenticated:
            try:
                await asyncio.sleep(WS_KEEPALIVE_INTERVAL)
                
                if self.ws and self.authenticated:
                    await self.ws.send(WS_KEEPALIVE_MESSAGE)
                    self.last_ping_time = time.time()
                    self.logger.debug("Sent keepalive ping")
                    
            except Exception as e:
                self.logger.error(f"Keepalive error: {e}")
                break
    
    async def message_handler(self):
        """
        Receive and process WebSocket messages
        
        Message format from Simply Plural:
        {
            "msg": "update",
            "target": "frontHistory|members|customFronts|...",
            "results": [
                {
                    "operationType": "insert|update|delete",
                    "id": "object_id",
                    "content": { ... }
                }
            ]
        }
        """
        while self.running and self.ws and self.authenticated:
            try:
                message_str = await self.ws.recv()
                self.last_message_time = time.time()
                self.messages_received += 1
                
                self.logger.debug(f"Received message: {message_str[:200]}...")
                
                # Skip keepalive responses and auth messages
                if isinstance(message_str, str) and (
                    "pong" in message_str.lower() or
                    "authenticated" in message_str.lower()
                ):
                    self.logger.debug("Skipping keepalive/auth response")
                    continue
                
                # Parse JSON message
                try:
                    message_data = json.loads(message_str)
                except json.JSONDecodeError:
                    self.logger.warning(f"Non-JSON message received: {message_str}")
                    continue
                
                # Parse as update message
                update_msg = WSUpdateMessage.from_dict(message_data)
                
                if not update_msg.is_update_message():
                    self.logger.debug(f"Non-update message: {update_msg.msg_type}")
                    continue
                
                # Process each result in the update
                for result_data in update_msg.results:
                    result = WSUpdateResult.from_dict(result_data)
                    
                    self.logger.info(
                        f"Update: {update_msg.target} - {result.operation_type} - {result.object_id}"
                    )
                    
                    if self.debug:
                        self.logger.debug(f"Content: {json.dumps(result.content, indent=2)}")
                    
                    # Notify daemon via callback
                    if self.update_callback:
                        try:
                            await self.update_callback(
                                update_msg.target,
                                result.operation_type,
                                result.object_id,
                                result.content
                            )
                        except Exception as e:
                            self.logger.error(f"Error in update callback: {e}")
                
            except websockets.exceptions.ConnectionClosed:
                self.logger.warning("WebSocket connection closed")
                break
            except Exception as e:
                self.logger.error(f"Message handler error: {e}")
                break
    
    async def run(self):
        """
        Main run loop with auto-reconnect
        
        Maintains connection, handles reconnection with exponential backoff
        """
        self.running = True
        
        while self.running:
            try:
                # Connect and authenticate
                if await self.connect():
                    # Start keepalive and message handler
                    tasks = [
                        asyncio.create_task(self.keepalive_loop()),
                        asyncio.create_task(self.message_handler())
                    ]
                    
                    # Wait for either task to complete (indicating disconnection)
                    done, pending = await asyncio.wait(
                        tasks,
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    # Cancel remaining tasks
                    for task in pending:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                    
                    # Clean up connection
                    await self.disconnect()
                
                # If we're still running, reconnect with backoff
                if self.running:
                    self.reconnect_count += 1
                    self.logger.info(
                        f"Reconnecting in {self.reconnect_delay}s (attempt {self.reconnect_count})"
                    )
                    await asyncio.sleep(self.reconnect_delay)
                    
                    # Exponential backoff
                    self.reconnect_delay = min(
                        self.reconnect_delay * WS_RECONNECT_MULTIPLIER,
                        WS_RECONNECT_MAX_DELAY
                    )
                
            except Exception as e:
                self.logger.error(f"Fatal error in run loop: {e}")
                if self.running:
                    await asyncio.sleep(self.reconnect_delay)
    
    async def stop(self):
        """Stop the WebSocket manager"""
        self.logger.info("Stopping WebSocket manager")
        self.running = False
        await self.disconnect()
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current WebSocket status
        
        Returns:
            Dictionary with connection status, uptime, stats
        """
        uptime = time.time() - self.connect_time if self.connect_time else 0
        
        return {
            'connected': self.authenticated and self.ws is not None,
            'authenticated': self.authenticated,
            'uptime': uptime,
            'last_ping': self.last_ping_time,
            'last_message': self.last_message_time,
            'messages_received': self.messages_received,
            'reconnect_count': self.reconnect_count,
            'reconnect_delay': self.reconnect_delay
        }


class DaemonState:
    """
    Maintains daemon state from WebSocket updates
    
    Stores in-memory cache of current fronters, members, and custom fronts
    for instant access by Unix socket clients.
    """
    
    def __init__(self, api_client=None, cache_manager=None, debug: bool = False):
        """
        Initialize daemon state
        
        Args:
            api_client: SimplyPluralAPI instance (optional, for initial data fetch)
            cache_manager: CacheManager instance (optional, for disk cache)
            debug: Enable debug logging
        """
        self.api = api_client
        self.cache = cache_manager
        self.debug = debug
        
        # In-memory state (always fresh from WebSocket)
        self.current_fronters = None
        self.members = {}
        self.custom_fronts = {}
        self.front_history = {}
        
        # Update timestamps
        self.last_update_times = {
            'fronters': 0,
            'members': 0,
            'custom_fronts': 0,
            'front_history': 0
        }
        
        # Statistics
        self.update_count = 0
        self.start_time = time.time()
        
        # Setup logging
        self.logger = logging.getLogger("DaemonState")
        if debug:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)
    
    def _seed_front_history(self, fronters_data):
        """Populate front_history from fronters so WebSocket updates merge correctly"""
        for entry in fronters_data:
            entry_id = entry.get('id') or entry.get('_id')
            if entry_id:
                self.front_history[entry_id] = entry.get('content', entry)
        self.last_update_times['front_history'] = time.time()
        self.logger.info(f"Seeded front_history with {len(self.front_history)} entries")

    async def initialize(self):
        """
        Initialize state with data from API or cache
        
        Called on daemon startup to populate initial state
        """
        self.logger.info("Initializing daemon state...")
        
        # Try to load from API if available
        if self.api:
            try:
                # Get current fronters
                fronters_data = await asyncio.to_thread(self.api.get_fronters)
                if fronters_data:
                    self.current_fronters = fronters_data
                    self.last_update_times['fronters'] = time.time()
                    self.logger.info(f"Loaded {len(fronters_data)} current fronters")

                    self._seed_front_history(fronters_data)

                    # Write to cache
                    if self.cache:
                        self.cache.set_fronters(fronters_data)
                
                # Get members
                members_data = await asyncio.to_thread(self.api.get_members)
                if members_data:
                    self.members = {m.get('id') or m.get('_id'): m for m in members_data}
                    self.last_update_times['members'] = time.time()
                    self.logger.info(f"Loaded {len(self.members)} members")
                    
                    # Write to cache
                    if self.cache:
                        self.cache.set_members(members_data)
                
                # Get custom fronts
                custom_fronts_data = await asyncio.to_thread(self.api.get_custom_fronts)
                if custom_fronts_data:
                    self.custom_fronts = {cf.get('id') or cf.get('_id'): cf for cf in custom_fronts_data}
                    self.last_update_times['custom_fronts'] = time.time()
                    self.logger.info(f"Loaded {len(self.custom_fronts)} custom fronts")
                    
                    # Write to cache
                    if self.cache:
                        self.cache.set_custom_fronts(custom_fronts_data)
                
            except Exception as e:
                self.logger.error(f"Error initializing from API: {e}")
                
                # Fallback to cache on error
                if self.cache:
                    self.logger.info("Attempting to load from cache as fallback...")
                    try:
                        cached_fronters = self.cache.get_fronters()
                        if cached_fronters:
                            self.current_fronters = cached_fronters
                            self._seed_front_history(cached_fronters)
                            self.logger.info(f"Loaded {len(cached_fronters)} fronters from cache")

                        cached_members = self.cache.get_members()
                        if cached_members:
                            self.members = {m.get('id') or m.get('_id'): m for m in cached_members}
                            self.logger.info(f"Loaded {len(self.members)} members from cache")

                        cached_custom_fronts = self.cache.get_custom_fronts()
                        if cached_custom_fronts:
                            self.custom_fronts = {cf.get('id') or cf.get('_id'): cf for cf in cached_custom_fronts}
                            self.logger.info(f"Loaded {len(self.custom_fronts)} custom fronts from cache")
                    except Exception as cache_error:
                        self.logger.error(f"Error loading from cache: {cache_error}")

        # If no API, try cache first
        elif self.cache:
            self.logger.info("No API client available, loading from cache...")
            try:
                cached_fronters = self.cache.get_fronters()
                if cached_fronters:
                    self.current_fronters = cached_fronters
                    self._seed_front_history(cached_fronters)
                    self.logger.info(f"Loaded {len(cached_fronters)} fronters from cache")
                
                cached_members = self.cache.get_members()
                if cached_members:
                    self.members = {m.get('id') or m.get('_id'): m for m in cached_members}
                    self.logger.info(f"Loaded {len(self.members)} members from cache")
                
                cached_custom_fronts = self.cache.get_custom_fronts()
                if cached_custom_fronts:
                    self.custom_fronts = {cf.get('id') or cf.get('_id'): cf for cf in cached_custom_fronts}
                    self.logger.info(f"Loaded {len(self.custom_fronts)} custom fronts from cache")
            except Exception as e:
                self.logger.error(f"Error loading from cache: {e}")
        
        self.logger.info("State initialization complete")
    
    async def handle_update(self, target: str, operation: str, obj_id: str, content: Dict[str, Any]):
        """
        Handle WebSocket update message
        
        Args:
            target: Collection name (frontHistory, members, etc.)
            operation: insert, update, or delete
            obj_id: Object ID
            content: Object data
        """
        self.update_count += 1
        self.logger.debug(f"Processing update: {target}/{operation}/{obj_id}")
        
        if target == "frontHistory":
            await self._handle_front_history_update(operation, obj_id, content)
        elif target == "members":
            await self._handle_member_update(operation, obj_id, content)
        elif target == "customFronts":
            await self._handle_custom_front_update(operation, obj_id, content)
        
        # Update timestamp
        collection_key = target.replace('frontHistory', 'front_history').replace('customFronts', 'custom_fronts')
        self.last_update_times[collection_key] = time.time()
    
    async def _handle_front_history_update(self, operation: str, obj_id: str, content: Dict[str, Any]):
        """Handle frontHistory updates"""
        if operation == "delete":
            if obj_id in self.front_history:
                del self.front_history[obj_id]
                self.logger.info(f"Deleted front history entry: {obj_id}")
        else:
            self.front_history[obj_id] = content
        
        # Rebuild current fronters list from live front history entries
        live_fronts = [
            entry for entry in self.front_history.values()
            if entry.get('live', False)
        ]
        
        # Sort by start time (most recent first)
        live_fronts.sort(key=lambda x: x.get('startTime', 0), reverse=True)
        
        self.current_fronters = live_fronts
        self.logger.info(f"Updated current fronters: {len(live_fronts)} live")
        
        # Write to disk cache
        if self.cache:
            try:
                self.cache.set_fronters(live_fronts)
                self.logger.debug("Updated fronters cache on disk")
            except Exception as e:
                self.logger.error(f"Error updating fronters cache: {e}")
    
    async def _handle_member_update(self, operation: str, obj_id: str, content: Dict[str, Any]):
        """Handle member updates"""
        if operation == "delete":
            if obj_id in self.members:
                del self.members[obj_id]
                self.logger.info(f"Deleted member: {obj_id}")
                
                # Remove from disk cache
                if self.cache:
                    try:
                        self.cache.invalidate_member(obj_id)
                        self.logger.debug(f"Invalidated member cache for {obj_id}")
                    except Exception as e:
                        self.logger.error(f"Error invalidating member cache: {e}")
        else:
            self.members[obj_id] = content
            name = content.get('content', {}).get('name', obj_id) if 'content' in content else content.get('name', obj_id)
            self.logger.info(f"Updated member: {name}")
            
            # Write to disk cache (individual member)
            if self.cache:
                try:
                    self.cache.set_member(obj_id, content)
                    self.logger.debug(f"Updated member cache for {name}")
                except Exception as e:
                    self.logger.error(f"Error updating member cache: {e}")
        
        # Update full members list in cache
        if self.cache:
            try:
                members_list = list(self.members.values())
                self.cache.set_members(members_list)
                self.logger.debug("Updated full members list cache")
            except Exception as e:
                self.logger.error(f"Error updating members list cache: {e}")
    
    async def _handle_custom_front_update(self, operation: str, obj_id: str, content: Dict[str, Any]):
        """Handle custom front updates"""
        if operation == "delete":
            if obj_id in self.custom_fronts:
                del self.custom_fronts[obj_id]
                self.logger.info(f"Deleted custom front: {obj_id}")
                
                # Remove from disk cache
                if self.cache:
                    try:
                        self.cache.invalidate_custom_front(obj_id)
                        self.logger.debug(f"Invalidated custom front cache for {obj_id}")
                    except Exception as e:
                        self.logger.error(f"Error invalidating custom front cache: {e}")
        else:
            self.custom_fronts[obj_id] = content
            name = content.get('content', {}).get('name', obj_id) if 'content' in content else content.get('name', obj_id)
            self.logger.info(f"Updated custom front: {name}")
            
            # Write to disk cache (individual custom front)
            if self.cache:
                try:
                    self.cache.set_custom_front(obj_id, content)
                    self.logger.debug(f"Updated custom front cache for {name}")
                except Exception as e:
                    self.logger.error(f"Error updating custom front cache: {e}")
        
        # Update full custom fronts list in cache
        if self.cache:
            try:
                custom_fronts_list = list(self.custom_fronts.values())
                self.cache.set_custom_fronts(custom_fronts_list)
                self.logger.debug("Updated full custom fronts list cache")
            except Exception as e:
                self.logger.error(f"Error updating custom fronts list cache: {e}")
    
    def get_fronters(self) -> Dict[str, Any]:
        """Get current fronters (instant, from memory)"""
        return {
            'fronters': self.current_fronters or [],
            'timestamp': self.last_update_times.get('fronters', 0)
        }
    
    def get_members(self) -> Dict[str, Any]:
        """Get all members (instant, from memory)"""
        return {
            'members': list(self.members.values()),
            'timestamp': self.last_update_times.get('members', 0)
        }
    
    def get_custom_fronts(self) -> Dict[str, Any]:
        """Get all custom fronts (instant, from memory)"""
        return {
            'custom_fronts': list(self.custom_fronts.values()),
            'timestamp': self.last_update_times.get('custom_fronts', 0)
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get daemon state status"""
        uptime = time.time() - self.start_time
        
        return {
            'uptime': uptime,
            'update_count': self.update_count,
            'fronters_count': len(self.current_fronters) if self.current_fronters else 0,
            'members_count': len(self.members),
            'custom_fronts_count': len(self.custom_fronts),
            'last_updates': self.last_update_times
        }


class UnixSocketServer:
    """
    Unix domain socket server for client communication
    
    Listens on /tmp/sp-daemon-{profile}.sock and handles client requests
    """
    
    def __init__(self, socket_path: str, daemon_state: DaemonState, ws_manager: WebSocketManager, debug: bool = False):
        """
        Initialize Unix socket server
        
        Args:
            socket_path: Path to Unix socket file
            daemon_state: DaemonState instance
            ws_manager: WebSocketManager instance
            debug: Enable debug logging
        """
        self.socket_path = socket_path
        self.state = daemon_state
        self.ws_manager = ws_manager
        self.debug = debug
        
        self.server = None
        self.running = False
        self.client_count = 0
        
        # Setup logging
        self.logger = logging.getLogger("UnixSocketServer")
        if debug:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)
    
    async def start(self):
        """Start the Unix socket server"""
        # Remove old socket file if it exists
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        self.logger.info(f"Starting Unix socket server on {self.socket_path}")
        
        self.server = await asyncio.start_unix_server(
            self.handle_client,
            path=self.socket_path
        )
        
        # Set permissions (user-only access)
        os.chmod(self.socket_path, 0o600)
        
        self.running = True
        self.logger.info("✓ Unix socket server started")
    
    async def stop(self):
        """Stop the Unix socket server"""
        self.logger.info("Stopping Unix socket server")
        self.running = False
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        # Remove socket file
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        self.logger.info("Unix socket server stopped")
    
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Handle a client connection
        
        Args:
            reader: Async stream reader
            writer: Async stream writer
        """
        client_id = self.client_count
        self.client_count += 1
        
        self.logger.debug(f"Client {client_id} connected")
        
        try:
            # Read request (with timeout)
            request_data = await asyncio.wait_for(reader.read(8192), timeout=5.0)
            
            if not request_data:
                self.logger.debug(f"Client {client_id} sent empty request")
                return
            
            request_str = request_data.decode('utf-8')
            self.logger.debug(f"Client {client_id} request: {request_str[:200]}")
            
            # Parse request
            try:
                request_dict = json.loads(request_str)
                request = Request.from_dict(request_dict)
            except Exception as e:
                error_response = Response.error("unknown", f"Invalid request: {e}")
                writer.write(error_response.to_json().encode('utf-8'))
                await writer.drain()
                return
            
            # Handle command
            response = await self.handle_command(request)
            
            # Send response
            writer.write(response.to_json().encode('utf-8'))
            await writer.drain()
            
            self.logger.debug(f"Client {client_id} response sent")
            
        except asyncio.TimeoutError:
            self.logger.warning(f"Client {client_id} timeout")
        except Exception as e:
            self.logger.error(f"Error handling client {client_id}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            self.logger.debug(f"Client {client_id} disconnected")
    
    async def handle_command(self, request: Request) -> Response:
        """
        Handle a command request
        
        Args:
            request: Request object
            
        Returns:
            Response object
        """
        try:
            command = request.command
            
            if command == CommandType.PING:
                return Response.success(request.request_id, {'pong': True})
            
            elif command == CommandType.STATUS:
                ws_status = self.ws_manager.get_status()
                state_status = self.state.get_status()
                
                return Response.success(request.request_id, {
                    'websocket': ws_status,
                    'state': state_status,
                    'socket_path': self.socket_path
                })
            
            elif command == CommandType.FRONTING:
                fronters_data = self.state.get_fronters()
                return Response.success(request.request_id, fronters_data)
            
            elif command == CommandType.MEMBERS:
                members_data = self.state.get_members()
                return Response.success(request.request_id, members_data)
            
            elif command == CommandType.CUSTOM_FRONTS:
                custom_fronts_data = self.state.get_custom_fronts()
                return Response.success(request.request_id, custom_fronts_data)
            
            elif command == CommandType.SWITCH:
                # TODO: Implement switch command (will use HTTP API)
                return Response.error(request.request_id, "Switch command not yet implemented")
            
            elif command == CommandType.RELOAD:
                # TODO: Implement reload command
                return Response.error(request.request_id, "Reload command not yet implemented")
            
            else:
                return Response.error(request.request_id, f"Unknown command: {command}")
                
        except Exception as e:
            self.logger.error(f"Error handling command {request.command}: {e}")
            return Response.error(request.request_id, str(e))


class SimplyPluralDaemon:
    """
    Main daemon orchestrator
    
    Combines WebSocket manager, daemon state, and Unix socket server
    """
    
    def __init__(self, api_token: str, socket_path: str, profile: str = "default", debug: bool = False, api_client=None, cache_manager=None):
        """
        Initialize daemon
        
        Args:
            api_token: Simply Plural API token
            socket_path: Path to Unix socket file
            profile: Profile name
            debug: Enable debug logging
            api_client: SimplyPluralAPI instance (optional)
            cache_manager: CacheManager instance (optional)
        """
        self.api_token = api_token
        self.socket_path = socket_path
        self.profile = profile
        self.debug = debug
        self.api_client = api_client
        self.cache_manager = cache_manager
        
        # Setup logging
        self.logger = logging.getLogger("SimplyPluralDaemon")
        if debug:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)
        
        # Components (initialized in start())
        self.state = None
        self.ws_manager = None
        self.socket_server = None
        
        self.running = False
    
    async def start(self):
        """Start the daemon"""
        self.logger.info(f"Starting Simply Plural daemon (profile: {self.profile})")
        
        # Initialize state with API client and cache manager
        self.state = DaemonState(api_client=self.api_client, cache_manager=self.cache_manager, debug=self.debug)
        await self.state.initialize()
        
        # Create WebSocket manager with update callback
        async def ws_update_callback(target, operation, obj_id, content):
            await self.state.handle_update(target, operation, obj_id, content)
        
        self.ws_manager = WebSocketManager(
            self.api_token,
            update_callback=ws_update_callback,
            debug=self.debug
        )
        
        # Create Unix socket server
        self.socket_server = UnixSocketServer(
            self.socket_path,
            self.state,
            self.ws_manager,
            debug=self.debug
        )
        
        # Start components
        await self.socket_server.start()
        
        self.running = True
        self.logger.info("✓ Daemon started successfully")
        
        # Run WebSocket manager (blocking)
        await self.ws_manager.run()
    
    async def stop(self):
        """Stop the daemon"""
        self.logger.info("Stopping daemon...")
        self.running = False
        
        # Stop components
        if self.ws_manager:
            await self.ws_manager.stop()
        
        if self.socket_server:
            await self.socket_server.stop()
        
        self.logger.info("Daemon stopped")


# Main entry point
async def main():
    """Main daemon entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Simply Plural Daemon")
    parser.add_argument('--profile', default='default', help='Profile name')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--token', help='API token (or set SP_API_TOKEN env var)')
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Get API token
    token = args.token or os.environ.get('SP_API_TOKEN')
    if not token:
        # Try to load from config
        try:
            from .config_manager import ConfigManager
            config = ConfigManager(args.profile)
            token = config.api_token
        except Exception as e:
            print(f"Error: No API token provided")
            print(f"  Set SP_API_TOKEN environment variable, or")
            print(f"  Use --token argument, or")
            print(f"  Configure via 'sp config --setup'")
            sys.exit(1)
    
    if not token:
        print("Error: API token not found in config")
        sys.exit(1)
    
    # Socket path
    socket_path = f"/tmp/sp-daemon-{args.profile}.sock"
    
    # Create API client and cache manager if config is available
    api_client_instance = None
    cache_manager_instance = None
    
    try:
        from .config_manager import ConfigManager
        from .cache_manager import CacheManager
        from .api_client import SimplyPluralAPI
        
        # Load config
        config = ConfigManager(args.profile)
        
        # Get profile cache directory
        cache_dir = config.get_profile_cache_dir()
        
        # Create cache manager
        cache_manager_instance = CacheManager(cache_dir, config)
        logging.info(f"Cache directory: {cache_dir}")
        
        # Create API client
        api_client_instance = SimplyPluralAPI(
            token,
            config_manager=config,
            cache_manager=cache_manager_instance,
            debug=args.debug
        )
        logging.info("API client and cache manager initialized")
        
    except Exception as e:
        logging.warning(f"Could not initialize API client/cache: {e}")
        logging.warning("Daemon will run with WebSocket only (no initial data fetch or disk cache)")
    
    # Create and run daemon
    daemon = SimplyPluralDaemon(
        token,
        socket_path,
        args.profile,
        args.debug,
        api_client=api_client_instance,
        cache_manager=cache_manager_instance
    )
    
    # Handle shutdown signals
    shutdown_event = asyncio.Event()
    
    def signal_handler():
        print("\nShutting down daemon...")
        shutdown_event.set()
    
    # Register signal handlers
    loop = asyncio.get_event_loop()
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)
    except (AttributeError, NotImplementedError):
        # Windows
        signal.signal(signal.SIGINT, lambda s, f: signal_handler())
    
    # Run daemon
    try:
        daemon_task = asyncio.create_task(daemon.start())
        await shutdown_event.wait()
        await daemon.stop()
        await daemon_task
    except KeyboardInterrupt:
        await daemon.stop()


def cli_main():
    """Entry point for 'python -m simplyplural.daemon'"""
    asyncio.run(main())


if __name__ == '__main__':
    cli_main()
