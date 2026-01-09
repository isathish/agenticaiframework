"""
Webhook Manager.

Features:
- Incoming webhooks
- Outgoing webhooks
- Signature verification
- Event routing
"""

import uuid
import time
import logging
import json
import hashlib
import hmac
import threading
from typing import Dict, Any, List, Callable

logger = logging.getLogger(__name__)


class WebhookManager:
    """
    Manages webhooks for integrations.
    
    Features:
    - Incoming webhooks
    - Outgoing webhooks
    - Signature verification
    - Event routing
    """
    
    def __init__(self):
        self.incoming_webhooks: Dict[str, Dict[str, Any]] = {}
        self.outgoing_webhooks: Dict[str, Dict[str, Any]] = {}
        self.event_handlers: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()
    
    def register_incoming_webhook(self,
                                  name: str,
                                  secret: str = None,
                                  allowed_events: List[str] = None) -> Dict[str, Any]:
        """Register an incoming webhook endpoint."""
        webhook_id = str(uuid.uuid4())
        
        webhook = {
            'id': webhook_id,
            'name': name,
            'secret': secret or hashlib.sha256(str(time.time()).encode()).hexdigest()[:32],
            'allowed_events': allowed_events or ['*'],
            'url': f"/webhooks/incoming/{webhook_id}",
            'created_at': time.time(),
            'total_received': 0
        }
        
        with self._lock:
            self.incoming_webhooks[webhook_id] = webhook
        
        logger.info("Registered incoming webhook: %s", name)
        return webhook
    
    def register_outgoing_webhook(self,
                                  name: str,
                                  url: str,
                                  events: List[str],
                                  secret: str = None,
                                  headers: Dict[str, str] = None) -> Dict[str, Any]:
        """Register an outgoing webhook."""
        webhook_id = str(uuid.uuid4())
        
        webhook = {
            'id': webhook_id,
            'name': name,
            'url': url,
            'events': events,
            'secret': secret,
            'headers': headers or {},
            'created_at': time.time(),
            'total_sent': 0,
            'last_status': None
        }
        
        with self._lock:
            self.outgoing_webhooks[webhook_id] = webhook
        
        logger.info("Registered outgoing webhook: %s -> %s", name, url)
        return webhook
    
    def verify_signature(self, webhook_id: str, payload: str, signature: str) -> bool:
        """Verify webhook signature."""
        webhook = self.incoming_webhooks.get(webhook_id)
        if not webhook:
            return False
        
        secret = webhook.get('secret')
        if not secret:
            return True
        
        expected = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(f"sha256={expected}", signature)
    
    def process_incoming(self,
                        webhook_id: str,
                        event_type: str,
                        payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming webhook."""
        webhook = self.incoming_webhooks.get(webhook_id)
        if not webhook:
            return {'error': 'Webhook not found'}
        
        # Check allowed events
        if '*' not in webhook['allowed_events'] and event_type not in webhook['allowed_events']:
            return {'error': 'Event type not allowed'}
        
        webhook['total_received'] += 1
        
        # Route to handlers
        handlers = self.event_handlers.get(event_type, []) + self.event_handlers.get('*', [])
        
        results = []
        for handler in handlers:
            try:
                result = handler(event_type, payload)
                results.append({'status': 'success', 'result': result})
            except Exception as e:  # noqa: BLE001 - Collect all handler errors
                results.append({'status': 'error', 'error': str(e)})
        
        return {
            'webhook_id': webhook_id,
            'event_type': event_type,
            'handlers_executed': len(handlers),
            'results': results
        }
    
    def send_webhook(self, event_type: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Send webhook to all registered endpoints for event type."""
        results = []
        
        for webhook_id, webhook in self.outgoing_webhooks.items():
            if event_type not in webhook['events'] and '*' not in webhook['events']:
                continue
            
            # Prepare payload
            body = {
                'event': event_type,
                'timestamp': time.time(),
                'payload': payload
            }
            
            # Sign if secret
            signature = None
            if webhook.get('secret'):
                signature = hmac.new(
                    webhook['secret'].encode(),
                    json.dumps(body).encode(),
                    hashlib.sha256
                ).hexdigest()
            
            # Simulate sending
            webhook['total_sent'] += 1
            webhook['last_status'] = 200  # Simulated
            
            results.append({
                'webhook_id': webhook_id,
                'name': webhook['name'],
                'url': webhook['url'],
                'status': 200,
                'signature': f"sha256={signature}" if signature else None
            })
        
        return results
    
    def add_event_handler(self, event_type: str, handler: Callable):
        """Add handler for incoming webhook events."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    def list_webhooks(self) -> Dict[str, List[Dict[str, Any]]]:
        """List all webhooks."""
        return {
            'incoming': [
                {
                    'id': w['id'],
                    'name': w['name'],
                    'url': w['url'],
                    'allowed_events': w['allowed_events'],
                    'total_received': w['total_received']
                }
                for w in self.incoming_webhooks.values()
            ],
            'outgoing': [
                {
                    'id': w['id'],
                    'name': w['name'],
                    'url': w['url'],
                    'events': w['events'],
                    'total_sent': w['total_sent'],
                    'last_status': w['last_status']
                }
                for w in self.outgoing_webhooks.values()
            ]
        }


__all__ = ['WebhookManager']
