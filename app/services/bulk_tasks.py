"""Service for managing bulk checklist tasks and monitoring progress."""

import json
import logging
from datetime import datetime
from typing import List

from celery.result import AsyncResult
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.schemas.bulk_checklist import BulkTaskInfo, BulkTasksListResponse, BulkChecklistCreateResponse


logger = logging.getLogger(__name__)


def get_all_bulk_tasks() -> BulkTasksListResponse:
    """
    Get all bulk checklist creation tasks with detailed information.
    
    This function discovers all tasks in the Celery backend and returns
    comprehensive information about each bulk checklist creation task.
    """
    # Get all task IDs from Celery's result backend
    task_ids = _discover_all_task_ids()
    
    # Filter for bulk checklist creation tasks only
    bulk_task_ids = _filter_bulk_tasks(task_ids)
    
    logger.info(f"Found {len(bulk_task_ids)} bulk checklist tasks")
    
    # Auto-cleanup failed tasks older than 20 minutes
    bulk_task_ids = _cleanup_old_failed_tasks(bulk_task_ids)
    
    # Get detailed information for each task
    tasks = []
    for task_id in bulk_task_ids:
        try:
            logger.info(f"Processing task details for: {task_id}")
            task_info = _get_task_details(task_id)
            if task_info:
                tasks.append(task_info)
                logger.info(f"✓ Successfully processed task: {task_id}")
            else:
                logger.warning(f"✗ No task info returned for: {task_id}")
        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            continue
    
    # Sort tasks by creation time (newest first)
    tasks.sort(key=lambda x: x.created_at, reverse=True)
    
    return BulkTasksListResponse(
        total=len(tasks),
        tasks=tasks
    )


def _discover_all_task_ids() -> List[str]:
    """Discover all task IDs from the Celery backend."""
    try:
        # For Redis backend, we can inspect all keys
        import redis
        
        # Get Redis connection from Celery config
        result_backend = celery_app.conf.result_backend
        broker_url = celery_app.conf.broker_url
        
        logger.info(f"Result backend: {result_backend}")
        logger.info(f"Broker URL: {broker_url}")
        
        # Try result backend first (where task results are stored)
        redis_url = result_backend if result_backend.startswith('redis://') else broker_url
        
        if redis_url.startswith('redis://'):
            redis_client = redis.from_url(redis_url)
            
            # Test connection
            redis_client.ping()
            logger.info(f"Connected to Redis at {redis_url}")
            
            # Get ALL keys first to see what's there
            all_keys = redis_client.keys('*')
            logger.info(f"Total keys in database: {len(all_keys)}")
            
            # Look for any task-related keys
            all_task_keys = [key.decode('utf-8') for key in all_keys if 'task' in key.decode('utf-8').lower()]
            logger.info(f"All task-related keys: {all_task_keys}")
            
            # Get all task result keys - try different patterns
            task_keys = []
            
            # Standard Celery result backend pattern
            meta_keys = redis_client.keys("celery-task-meta-*")
            task_keys.extend(meta_keys)
            logger.info(f"Found {len(meta_keys)} celery-task-meta-* keys")
            
            # Alternative patterns that might be used
            result_keys = redis_client.keys("celery-result-*")
            task_keys.extend(result_keys)
            logger.info(f"Found {len(result_keys)} celery-result-* keys")
            
            any_task_keys = redis_client.keys("*task*")
            task_keys.extend(any_task_keys)
            logger.info(f"Found {len(any_task_keys)} *task* keys")
            
            # Remove duplicates
            task_keys = list(set(task_keys))
            logger.info(f"Total unique task keys: {len(task_keys)}")
            
            # Extract task IDs from keys
            task_ids = []
            for key in task_keys:
                key_str = key.decode('utf-8')
                logger.debug(f"Processing key: {key_str}")
                
                if 'celery-task-meta-' in key_str:
                    task_id = key_str.replace('celery-task-meta-', '')
                    task_ids.append(task_id)
                    logger.debug(f"Extracted task ID: {task_id}")
                elif 'celery-result-' in key_str:
                    task_id = key_str.replace('celery-result-', '')
                    task_ids.append(task_id)
                    logger.debug(f"Extracted task ID from result: {task_id}")
                else:
                    logger.debug(f"Skipping non-task key: {key_str}")
            
            logger.info(f"Final task IDs extracted: {task_ids}")
            logger.info(f"Found {len(task_ids)} task IDs in Redis database")
            
            # If no tasks found in result backend, try broker database
            if len(task_ids) == 0 and result_backend != broker_url:
                logger.info("No tasks found in result backend, trying broker database...")
                broker_client = redis.from_url(broker_url)
                broker_task_keys = broker_client.keys("celery-task-meta-*")
                task_ids = [key.decode('utf-8').replace('celery-task-meta-', '') for key in broker_task_keys]
                logger.info(f"Found {len(task_ids)} task IDs in broker database")
            
            return task_ids
        else:
            # Fallback for other backends - this is less efficient
            logger.warning("Non-Redis broker detected, task discovery may be limited")
            return []
            
    except Exception as e:
        logger.error(f"Error discovering tasks: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return []


def _filter_bulk_tasks(task_ids: List[str]) -> List[str]:
    """Filter task IDs to only include bulk checklist creation tasks."""
    bulk_task_ids = []
    
    for task_id in task_ids:
        try:
            # Try to get task name from AsyncResult
            result = celery_app.AsyncResult(task_id)
            task_name = getattr(result, 'name', None) or result.name
            
            # Check if this is a bulk import task
            is_bulk_task = False
            
            # Method 1: Check task name
            if task_name and ('bulk_import' in task_name or 'create_checklist' in task_name):
                is_bulk_task = True
                logger.info(f"✓ Identified bulk task by name: {task_id} ({task_name})")
            
            # Method 2: Check extracted name from Redis
            elif not task_name or task_name == 'None':
                extracted_name = _extract_task_name_from_redis(task_id)
                if extracted_name and ('bulk_import' in extracted_name or 'create_checklist' in extracted_name):
                    is_bulk_task = True
                    logger.info(f"✓ Identified bulk task from Redis: {task_id} ({extracted_name})")
                else:
                    # Method 3: Check task result content for bulk import indicators
                    task_result = _get_task_result_from_redis(task_id)
                    if task_result and _is_bulk_import_result(task_result):
                        is_bulk_task = True
                        logger.info(f"✓ Identified bulk task by result content: {task_id}")
            
            # Method 3: Check task result content for bulk import indicators (for named tasks that don't match patterns)
            else:
                task_result = _get_task_result_from_redis(task_id)
                if task_result and _is_bulk_import_result(task_result):
                    is_bulk_task = True
                    logger.info(f"✓ Identified bulk task by result content: {task_id}")
            
            if is_bulk_task:
                bulk_task_ids.append(task_id)
            else:
                logger.debug(f"✗ Skipping non-bulk task: {task_id} (name: {task_name})")
                    
        except Exception as e:
            logger.warning(f"Error filtering task {task_id}: {e}")
            continue
    
    logger.info(f"Filtered to {len(bulk_task_ids)} bulk checklist tasks")
    return bulk_task_ids


def _cleanup_old_failed_tasks(task_ids: List[str]) -> List[str]:
    """Remove failed tasks older than 20 minutes from the task list."""
    from datetime import datetime, timedelta
    import redis
    import json
    
    cleaned_task_ids = []
    cleanup_threshold = datetime.utcnow() - timedelta(minutes=5)
    
    try:
        result_backend = celery_app.conf.result_backend
        if result_backend.startswith('redis://'):
            redis_client = redis.from_url(result_backend)
            
            for task_id in task_ids:
                try:
                    task_key = f"celery-task-meta-{task_id}"
                    task_data = redis_client.get(task_key)
                    
                    if task_data:
                        data = json.loads(task_data.decode('utf-8'))
                        
                        # Check if task is failed and old
                        if data.get('status') == 'FAILURE':
                            date_done_str = data.get('date_done')
                            if date_done_str:
                                try:
                                    # Parse ISO datetime
                                    date_done = datetime.fromisoformat(date_done_str.replace('Z', '+00:00'))
                                    if date_done < cleanup_threshold:
                                        logger.info(f"Cleaning up old failed task: {task_id} (failed at {date_done})")
                                        # Delete the task from Redis
                                        redis_client.delete(task_key)
                                        continue  # Skip this task
                                except ValueError:
                                    logger.warning(f"Could not parse date for task {task_id}: {date_done_str}")
                    
                    # Keep tasks that are not old failed tasks
                    cleaned_task_ids.append(task_id)
                    
                except Exception as e:
                    logger.warning(f"Error checking task {task_id} for cleanup: {e}")
                    cleaned_task_ids.append(task_id)  # Keep on error
                    
    except Exception as e:
        logger.error(f"Error during task cleanup: {e}")
        return task_ids  # Return original list on error
    
    cleaned_count = len(task_ids) - len(cleaned_task_ids)
    if cleaned_count > 0:
        logger.info(f"Cleaned up {cleaned_count} old failed tasks")
    
    return cleaned_task_ids


def _get_task_result_from_redis(task_id: str) -> dict:
    """Get task result data from Redis."""
    try:
        import redis
        import json
        
        result_backend = celery_app.conf.result_backend
        if result_backend.startswith('redis://'):
            redis_client = redis.from_url(result_backend)
            task_key = f"celery-task-meta-{task_id}"
            task_data = redis_client.get(task_key)
            
            if task_data:
                data = json.loads(task_data.decode('utf-8'))
                return data.get('result', {})
    
    except Exception as e:
        logger.warning(f"Could not get task result from Redis for {task_id}: {e}")
    
    return {}


def _is_bulk_import_result(result: dict) -> bool:
    """Check if task result indicates a bulk import task."""
    if not isinstance(result, dict):
        return False
    
    # Check for bulk import specific fields
    bulk_indicators = [
        'checklist_title',
        'sections_created', 
        'questions_created',
        'total_rows_processed',
        'warnings',
        'checklist_id'
    ]
    
    # If result has multiple bulk import indicators, it's likely a bulk import task
    indicator_count = sum(1 for indicator in bulk_indicators if indicator in result)
    
    # Also check for bulk import related error messages
    if 'exc_type' in result:
        exc_type = result.get('exc_type', '')
        if 'ValidationError' in exc_type or 'bulk_import' in str(result):
            indicator_count += 1
    
    return indicator_count >= 2  # Need at least 2 indicators to be confident


def _extract_task_name_from_redis(task_id: str) -> str:
    """Extract task name from Redis data when not available in AsyncResult."""
    try:
        import redis
        import json
        
        result_backend = celery_app.conf.result_backend
        if result_backend.startswith('redis://'):
            redis_client = redis.from_url(result_backend)
            task_key = f"celery-task-meta-{task_id}"
            task_data = redis_client.get(task_key)
            
            if task_data:
                data = json.loads(task_data.decode('utf-8'))
                
                # Check if task name is in the data
                if 'name' in data:
                    return data['name']
                
                # Check if task name is in the error message (for NotRegistered errors)
                result = data.get('result', {})
                if isinstance(result, dict) and 'exc_message' in result:
                    exc_message = result['exc_message']
                    if isinstance(exc_message, list) and len(exc_message) > 0:
                        # Task name is often in the exception message for NotRegistered errors
                        potential_name = exc_message[0]
                        if 'bulk_import' in potential_name or 'create_checklist' in potential_name:
                            return potential_name
                
                # Check if task_id contains the name
                if 'task_id' in data:
                    return data['task_id']
    
    except Exception as e:
        logger.warning(f"Could not extract task name from Redis for {task_id}: {e}")
    
    return 'UNKNOWN'


def _get_task_details(task_id: str) -> BulkTaskInfo | None:
    """Get detailed information for a specific task."""
    try:
        async_result = celery_app.AsyncResult(task_id)
        state = async_result.state
        
        # Initialize task info with defaults
        task_info_dict = {
            "task_id": task_id,
            "celery_state": state,
            "status": "pending",
            "detail": "Task queued or waiting for worker execution.",
            "created_at": "",
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
            "actor_id": None,
            "checklist_title": "Unknown",
            "checklist_description": None,
            "file_name": "Unknown",
            "checklist_type_code": "compliance",
        }
        
        # Get task metadata from Redis if available
        _extract_task_metadata(task_id, task_info_dict)
        
        # Process task state and result
        _process_task_state(async_result, task_info_dict)
        
        return BulkTaskInfo(**task_info_dict)
        
    except Exception as e:
        logger.error(f"Error getting details for task {task_id}: {e}")
        return None


def _extract_task_metadata(task_id: str, task_info_dict: dict) -> None:
    """Extract task metadata from Redis."""
    try:
        import redis
        
        # Try result backend first, then broker
        result_backend = celery_app.conf.result_backend
        broker_url = celery_app.conf.broker_url
        
        redis_url = result_backend if result_backend.startswith('redis://') else broker_url
        
        if redis_url.startswith('redis://'):
            redis_client = redis.from_url(redis_url)
            task_key = f"celery-task-meta-{task_id}"
            task_data = redis_client.get(task_key)
            
            # If not found in result backend, try broker
            if not task_data and result_backend != broker_url:
                broker_client = redis.from_url(broker_url)
                task_data = broker_client.get(task_key)
            
            if task_data:
                meta = json.loads(task_data.decode('utf-8'))
                task_info_dict["created_at"] = meta.get("date_done", "")
                
                # Extract task arguments from the task
                task_args = meta.get("args", [])
                if len(task_args) >= 5:
                    task_info_dict["actor_id"] = task_args[0]
                    task_info_dict["checklist_title"] = task_args[3] if len(task_args) > 3 else "Unknown"
                    task_info_dict["checklist_description"] = task_args[4] if len(task_args) > 4 else None
                    task_info_dict["checklist_type_code"] = task_args[5] if len(task_args) > 5 else "compliance"
                    
                    # Extract file name from args if available
                    if len(task_args) > 2:
                        task_info_dict["file_name"] = task_args[2]
                        
    except Exception as e:
        logger.warning(f"Could not extract task metadata for {task_id}: {e}")


def _process_task_state(async_result: AsyncResult, task_info_dict: dict) -> None:
    """Process task state and update task info accordingly."""
    state = async_result.state
    
    if state == "PENDING":
        task_info_dict["detail"] = "Task is pending execution."
        task_info_dict["status"] = "pending"
        
    elif state == "STARTED":
        task_info_dict["detail"] = "Task has started processing."
        task_info_dict["status"] = "started"
        task_info_dict["started_at"] = datetime.utcnow().isoformat() + "Z"
        
    elif state == "SUCCESS":
        payload = async_result.result or {}
        if isinstance(payload, dict):
            task_info_dict["status"] = payload.get("status", "success")
            task_info_dict["detail"] = payload.get("message", "Bulk import task completed.")
            
            # Parse the result if it's a valid response
            try:
                task_info_dict["result"] = BulkChecklistCreateResponse.model_validate(payload)
                
                # Update file name from result if available
                if hasattr(task_info_dict["result"], "file_name"):
                    task_info_dict["file_name"] = task_info_dict["result"].file_name
                    
            except Exception as e:
                logger.warning(f"Could not parse task result: {e}")
                
            task_info_dict["completed_at"] = datetime.utcnow().isoformat() + "Z"
        else:
            task_info_dict["status"] = "failed"
            task_info_dict["error"] = "Unexpected task result format."
            task_info_dict["detail"] = "Task completed with an invalid result payload."
            task_info_dict["completed_at"] = datetime.utcnow().isoformat() + "Z"
            
    elif state in ("FAILURE", "RETRY"):
        task_info_dict["status"] = "failed"
        task_info_dict["error"] = str(async_result.result)
        task_info_dict["detail"] = "Bulk import task failed."
        task_info_dict["completed_at"] = datetime.utcnow().isoformat() + "Z"


def get_stuck_tasks(timeout_minutes: int = 20) -> List[BulkTaskInfo]:
    """
    Get tasks that have been pending for longer than the specified timeout.
    
    Args:
        timeout_minutes: Maximum allowed time for a task to be in pending state
        
    Returns:
        List of stuck tasks
    """
    all_tasks_response = get_all_bulk_tasks()
    stuck_tasks = []
    
    for task in all_tasks_response.tasks:
        if task.status == "pending" and task.created_at:
            try:
                # Parse creation time and check if it's older than timeout
                created_time = datetime.fromisoformat(task.created_at.replace('Z', '+00:00'))
                time_diff = datetime.utcnow().replace(tzinfo=created_time.tzinfo) - created_time
                
                if time_diff.total_seconds() > (timeout_minutes * 60):
                    stuck_tasks.append(task)
                    
            except Exception as e:
                logger.warning(f"Could not parse creation time for task {task.task_id}: {e}")
    
    return stuck_tasks
