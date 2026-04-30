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
    
    # Get detailed information for each task
    tasks = []
    for task_id in bulk_task_ids:
        try:
            task_info = _get_task_details(task_id)
            if task_info:
                tasks.append(task_info)
        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}")
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
        redis_url = celery_app.conf.broker_url
        if redis_url.startswith('redis://'):
            redis_client = redis.from_url(redis_url)
            
            # Get all task result keys
            task_keys = redis_client.keys("celery-task-meta-*")
            task_ids = [key.decode('utf-8').replace('celery-task-meta-', '') for key in task_keys]
            
            logger.info(f"Found {len(task_ids)} task IDs in Redis")
            return task_ids
        else:
            # Fallback for other backends - this is less efficient
            logger.warning("Non-Redis broker detected, task discovery may be limited")
            return []
            
    except Exception as e:
        logger.error(f"Error discovering tasks: {e}")
        return []


def _filter_bulk_tasks(task_ids: List[str]) -> List[str]:
    """Filter task IDs to only include bulk checklist creation tasks."""
    bulk_task_ids = []
    for task_id in task_ids:
        try:
            async_result = celery_app.AsyncResult(task_id)
            if async_result.name == "app.tasks.bulk_import.create_checklist_task":
                bulk_task_ids.append(task_id)
        except Exception:
            continue
    
    return bulk_task_ids


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
        
        redis_url = celery_app.conf.broker_url
        if redis_url.startswith('redis://'):
            redis_client = redis.from_url(redis_url)
            task_key = f"celery-task-meta-{task_id}"
            task_data = redis_client.get(task_key)
            
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
