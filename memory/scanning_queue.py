"""Durable Scanning Queue (DSQ) Manager using PostgreSQL."""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
import logging

class ScanningQueue:
    """Manager for persistent scanning tasks in PostgreSQL."""
    
    def __init__(self, conversation_store):
        """Initialize scanning queue.
        
        Args:
            conversation_store: Instance of ConversationStore
        """
        self.store = conversation_store
        self.logger = logging.getLogger(__name__)

    def add_targets(self, 
                   conversation_id: str, 
                   targets: List[str], 
                   tool_name: str, 
                   command_name: Optional[str] = None,
                   parameters: Optional[Dict] = None) -> int:
        """Add multiple targets to the scan queue.
        
        Args:
            conversation_id: Conversation ID
            targets: List of hosts/IPs to scan
            tool_name: Tool to use
            command_name: Optional tool command
            parameters: Base parameters for the tool
            
        Returns:
            Number of targets added
        """
        conn = self.store._get_connection()
        try:
            cursor = conn.cursor()
            query = """
                INSERT INTO scan_tasks 
                (conversation_id, host, tool_name, command_name, parameters, status)
                VALUES (%s, %s, %s, %s, %s, 'pending')
                ON CONFLICT DO NOTHING
            """
            
            count = 0
            for target in targets:
                cursor.execute(query, (
                    conversation_id, 
                    target, 
                    tool_name, 
                    command_name, 
                    json.dumps(parameters or {}),
                ))
                count += 1
                
            conn.commit()
            cursor.close()
            return count
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Failed to add targets to queue: {e}")
            return 0
        finally:
            conn.close()

    def claim_task(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Atomically claim a pending task for scanning.
        
        Uses PostgreSQL 'FOR UPDATE SKIP LOCKED' for safe concurrent access.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Task details or None if no tasks available
        """
        conn = self.store._get_connection()
        try:
            cursor = conn.cursor()
            
            # Select and lock one pending task
            select_query = """
                WITH cte AS (
                  SELECT id FROM scan_tasks
                  WHERE conversation_id = %s AND status = 'pending'
                  ORDER BY priority DESC, created_at ASC
                  LIMIT 1
                  FOR UPDATE SKIP LOCKED
                )
                UPDATE scan_tasks
                SET status = 'scanning', updated_at = NOW()
                FROM cte
                WHERE scan_tasks.id = cte.id
                RETURNING scan_tasks.id, scan_tasks.host, scan_tasks.tool_name, 
                          scan_tasks.command_name, scan_tasks.parameters
            """
            
            cursor.execute(select_query, (conversation_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
                
            task = {
                "id": str(row[0]),
                "host": row[1],
                "tool_name": row[2],
                "command_name": row[3],
                "parameters": row[4] if isinstance(row[4], dict) else json.loads(row[4] or '{}')
            }
            
            conn.commit()
            cursor.close()
            return task
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Failed to claim task: {e}")
            return None
        finally:
            conn.close()

    def update_result(self, task_id: str, success: bool, result: Any = None, error: str = None):
        """Update task status and store result.
        
        Args:
            task_id: Task UUID
            success: Whether scan was successful
            result: Parsed tool output
            error: Error message if failed
        """
        conn = self.store._get_connection()
        try:
            cursor = conn.cursor()
            status = 'done' if success else 'error'
            
            query = """
                UPDATE scan_tasks
                SET status = %s, result = %s, error = %s, updated_at = NOW()
                WHERE id = %s
            """
            cursor.execute(query, (status, json.dumps(result or {}), error, task_id))
            
            conn.commit()
            cursor.close()
            
            # If successful, promote results to findings table
            if success and result:
                self.promote_findings(task_id)
                
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Failed to update task result: {e}")
        finally:
            conn.close()

    def promote_findings(self, task_id: str):
        """Extract important findings from scan result and promote to conversation findings table."""
        conn = self.store._get_connection()
        try:
            cursor = conn.cursor()
            
            # Get task details
            cursor.execute("SELECT conversation_id, host, tool_name, result FROM scan_tasks WHERE id = %s", (task_id,))
            row = cursor.fetchone()
            if not row: return
            
            conv_id, host, tool, result_data = row
            if isinstance(result_data, str): result_data = json.loads(result_data)
            
            # Logic to extract findings based on tool type
            # Example for nmap: promote open ports
            findings = []
            
            if 'open_ports' in result_data:
                for port_info in result_data['open_ports']:
                    port = port_info.get('port')
                    service = port_info.get('service', 'unknown')
                    findings.append({
                        'type': 'port',
                        'value': str(port),
                        'metadata': {'service': service, 'host': host}
                    })
            
            # Insert findings
            insert_query = """
                INSERT INTO findings (conversation_id, type, value, source_tool, target, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            for f in findings:
                cursor.execute(insert_query, (
                    conv_id, f['type'], f['value'], tool, host, json.dumps(f['metadata'])
                ))
            
            conn.commit()
            cursor.close()
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Failed to promote findings: {e}")
        finally:
            conn.close()

    def get_progress(self, conversation_id: str) -> Dict[str, Any]:
        """Get scan progress summary for a conversation.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Dictionary with completion stats
        """
        conn = self.store._get_connection()
        try:
            cursor = conn.cursor()
            query = """
                SELECT status, COUNT(*) 
                FROM scan_tasks 
                WHERE conversation_id = %s 
                GROUP BY status
            """
            cursor.execute(query, (conversation_id,))
            rows = cursor.fetchall()
            
            stats = {row[0]: row[1] for row in rows}
            total = sum(stats.values())
            done = stats.get('done', 0) + stats.get('error', 0)
            
            cursor.close()
            return {
                "total": total,
                "pending": stats.get('pending', 0),
                "scanning": stats.get('scanning', 0),
                "done": stats.get('done', 0),
                "error": stats.get('error', 0),
                "percent_complete": round((done / total * 100), 2) if total > 0 else 0
            }
        except Exception:
            return {"total": 0, "percent_complete": 0}
        finally:
            conn.close()
