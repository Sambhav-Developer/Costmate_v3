import asyncio
import json
from typing import Dict, Any, Optional
from app.services.graph.graph import costmate_graph
from app.core.logging import logger

class SessionManager:
    def __init__(self):
        # Maps session_id -> { "queue": asyncio.Queue, "task": asyncio.Task }
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def get_queue(self, session_id: str) -> Optional[asyncio.Queue]:
        if session_id in self.sessions:
            return self.sessions[session_id]["queue"]
        return None

    def create_session(self, session_id: str) -> asyncio.Queue:
        queue = asyncio.Queue()
        self.sessions[session_id] = {
            "queue": queue,
            "task": None
        }
        return queue

    def cancel_session(self, session_id: str):
        """Cancels any running background task for the session."""
        if session_id in self.sessions:
            task = self.sessions[session_id].get("task")
            if task and not task.done():
                logger.info(f"[{session_id}] Canceling running background task.")
                task.cancel()
            del self.sessions[session_id]

    async def get_status_stream(self, session_id: str):
        queue = self.get_queue(session_id)
        if not queue:
            queue = self.create_session(session_id)
        try:
            while True:
                event = await queue.get()
                yield json.dumps(event)
                if event.get("status") in ["completed", "failed", "paused_qa"]:
                    # Do not break on paused_qa if we expect to resume, 
                    # but typically the client reconnects. Let's not break on paused_qa.
                    if event.get("status") != "paused_qa":
                        break
        except asyncio.CancelledError:
            pass

    def _save_to_db(self, session_id: str, state: dict, user_id: Optional[int] = None):
        from app.db.postgres import SessionLocal
        from app.models.estimation import EstimationSession
        from sqlalchemy.dialects.postgresql import insert
        
        try:
            db = SessionLocal()
            try:
                if user_id is not None:
                    stmt = insert(EstimationSession).values(
                        id=session_id,
                        user_id=user_id,
                        state=state
                    )
                    do_update_stmt = stmt.on_conflict_do_update(
                        index_elements=['id'],
                        set_=dict(
                            state=stmt.excluded.state,
                            updated_at=stmt.excluded.updated_at
                        )
                    )
                    db.execute(do_update_stmt)
                else:
                    db.query(EstimationSession).filter(EstimationSession.id == session_id).update({"state": state})
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[{session_id}] Failed to save estimation session to database: {e}")

    async def restore_session_if_needed(self, session_id: str, user_id: Optional[int] = None) -> bool:
        """Restores a session from PostgreSQL to MemorySaver if missing in memory mapping."""
        if session_id in self.sessions:
            return True
            
        from app.db.postgres import SessionLocal
        from app.models.estimation import EstimationSession
        
        try:
            db = SessionLocal()
            try:
                query = db.query(EstimationSession).filter(EstimationSession.id == session_id)
                if user_id is not None:
                    query = query.filter(EstimationSession.user_id == user_id)
                    
                session_obj = query.first()
                if not session_obj:
                    return False
                    
                state_dict = session_obj.state
            finally:
                db.close()
                        
            # Seed/restore in memory checkpointer
            config = {"configurable": {"thread_id": session_id}}
            await costmate_graph.aupdate_state(config, state_dict)
            
            # Recreate session in memory mapping
            self.create_session(session_id)
            logger.info(f"[{session_id}] Restored session state from DB to memory saver.")
            return True
        except Exception as e:
            logger.error(f"[{session_id}] Failed to restore session from database: {e}")
            return False

    def start_session(
        self, 
        session_id: str, 
        uploaded_file_path: str, 
        uploaded_page_paths: list[str], 
        original_filename: str = "", 
        user_id: int = 1,
        project_name: str = "",
        intake_data: dict = None,
        specifications_text: str = ""
    ):
        """Starts the LangGraph execution in the background."""
        queue = self.get_queue(session_id)
        if not queue:
            queue = self.create_session(session_id)

        # Set initial state
        initial_state = {
            "session_id": session_id,
            "uploaded_file_path": uploaded_file_path,
            "original_filename": original_filename,
            "uploaded_page_paths": uploaded_page_paths,
            "project_name": project_name,
            "intake_data": intake_data,
            "specifications_text": specifications_text,
            "status": "processing",
            "current_step": "upload_completed",
            "progress_pct": 5,
            "raw_ocr_text": "",
            "parsed_image_data": {},
            "floor_plan": {},
            "dimensions": {},
            "elements": {},
            "qa_prefilled": {},
            "qa_verified": {},
            "civil_quantities": {},
            "validation_passed": False,
            "excel_file_path": None,
            "error": None
        }

        # Start background task
        task = asyncio.create_task(self._run_graph(session_id, initial_state, user_id))
        self.sessions[session_id]["task"] = task
        logger.info(f"[{session_id}] Background task started for graph execution.")
        # Save initial state to DB
        self._save_to_db(session_id, initial_state, user_id)

    def resume_session(self, session_id: str, qa_verified: dict):
        """Resumes a paused LangGraph execution with user Q&A answers."""
        queue = self.get_queue(session_id)
        if not queue:
            queue = self.create_session(session_id)

        # Start background task to update state and resume
        task = asyncio.create_task(self._resume_graph(session_id, qa_verified))
        self.sessions[session_id]["task"] = task
        logger.info(f"[{session_id}] Background task started to resume graph execution.")

    async def _run_graph(self, session_id: str, initial_state: dict, user_id: int):
        queue = self.sessions[session_id]["queue"]
        config = {"configurable": {"thread_id": session_id}}
        
        # Send initial progress
        await queue.put({
            "step": "upload_completed",
            "progress": 5,
            "status": "processing"
        })

        try:
            async for event in costmate_graph.astream(initial_state, config, stream_mode="updates"):
                await self._process_graph_event(session_id, queue, event)
                # Save incremental changes to DB
                state_snapshot = await costmate_graph.aget_state(config)
                if state_snapshot.values:
                    self._save_to_db(session_id, state_snapshot.values, user_id)

            # Check if graph is paused at an interrupt node
            state_snapshot = await costmate_graph.aget_state(config)
            if state_snapshot.next and "interrupt_node" in state_snapshot.next:
                logger.info(f"[{session_id}] Graph paused at interrupt_node.")
                # Read prefilled values
                qa_prefilled = state_snapshot.values.get("qa_prefilled", {})
                await queue.put({
                    "step": "paused_qa",
                    "progress": 50,
                    "status": "paused_qa",
                    "qa_prefilled": qa_prefilled
                })
                # Save final paused state to DB
                self._save_to_db(session_id, state_snapshot.values, user_id)
            else:
                logger.info(f"[{session_id}] Graph run finished first phase without interrupt.")

        except Exception as e:
            logger.error(f"[{session_id}] Graph execution error: {e}", exc_info=True)
            await queue.put({
                "step": "error",
                "progress": 0,
                "status": "failed",
                "error": str(e)
            })

    async def _resume_graph(self, session_id: str, qa_verified: dict):
        queue = self.sessions[session_id]["queue"]
        config = {"configurable": {"thread_id": session_id}}

        try:
            # Update state with user answers and resume graph
            logger.info(f"[{session_id}] Resuming graph by updating state with verified QA.")
            await costmate_graph.aupdate_state(
                config,
                {
                    "qa_verified": qa_verified,
                    "raw_ocr_text": qa_verified.get("raw_ocr_text", "")
                },
                as_node="interrupt_node"
            )
            
            # Save updated state to DB
            state_snapshot = await costmate_graph.aget_state(config)
            if state_snapshot.values:
                self._save_to_db(session_id, state_snapshot.values)

            # Continue streaming from where it left off
            async for event in costmate_graph.astream(None, config, stream_mode="updates"):
                await self._process_graph_event(session_id, queue, event)
                # Save incremental changes to DB
                state_snapshot = await costmate_graph.aget_state(config)
                if state_snapshot.values:
                    self._save_to_db(session_id, state_snapshot.values)

            # Check final state
            state_snapshot = await costmate_graph.aget_state(config)
            values = state_snapshot.values
            if values.get("status") == "completed":
                logger.info(f"[{session_id}] Graph successfully run to completion.")
                await queue.put({
                    "step": "completed",
                    "progress": 100,
                    "status": "completed",
                    "excel_file_path": values.get("excel_file_path")
                })
            else:
                logger.warning(f"[{session_id}] Graph finished run but status is not completed: {values.get('status')}")
                await queue.put({
                    "step": "completed",
                    "progress": 100,
                    "status": values.get("status", "completed")
                })
            
            # Save final completed state to DB
            self._save_to_db(session_id, values)

        except Exception as e:
            logger.error(f"[{session_id}] Resume graph execution error: {e}", exc_info=True)
            await queue.put({
                "step": "error",
                "progress": 0,
                "status": "failed",
                "error": str(e)
            })

    async def _resume_running_graph(self, session_id: str, user_id: int):
        """Resumes a graph execution that was running when the server restarted."""
        queue = self.sessions[session_id]["queue"]
        config = {"configurable": {"thread_id": session_id}}

        try:
            logger.info(f"[{session_id}] Resuming previously interrupted graph run...")
            # Continue streaming from where it left off
            async for event in costmate_graph.astream(None, config, stream_mode="updates"):
                await self._process_graph_event(session_id, queue, event)
                # Save incremental changes to DB
                state_snapshot = await costmate_graph.aget_state(config)
                if state_snapshot.values:
                    self._save_to_db(session_id, state_snapshot.values, user_id)

            # Check final state after completion or interrupt
            state_snapshot = await costmate_graph.aget_state(config)
            if state_snapshot.next and "interrupt_node" in state_snapshot.next:
                logger.info(f"[{session_id}] Graph paused at interrupt_node after resumption.")
                qa_prefilled = state_snapshot.values.get("qa_prefilled", {})
                await queue.put({
                    "step": "paused_qa",
                    "progress": 50,
                    "status": "paused_qa",
                    "qa_prefilled": qa_prefilled
                })
                self._save_to_db(session_id, state_snapshot.values, user_id)
            else:
                values = state_snapshot.values
                if values.get("status") == "completed":
                    logger.info(f"[{session_id}] Graph successfully run to completion after resumption.")
                    await queue.put({
                        "step": "completed",
                        "progress": 100,
                        "status": "completed",
                        "excel_file_path": values.get("excel_file_path")
                    })
                else:
                    logger.warning(f"[{session_id}] Graph finished run but status is not completed: {values.get('status')}")
                    await queue.put({
                        "step": "completed",
                        "progress": 100,
                        "status": values.get("status", "completed")
                    })
                self._save_to_db(session_id, values, user_id)

        except Exception as e:
            logger.error(f"[{session_id}] Resume running graph execution error: {e}", exc_info=True)
            await queue.put({
                "step": "error",
                "progress": 0,
                "status": "failed",
                "error": str(e)
            })

    async def _process_graph_event(self, session_id: str, queue: asyncio.Queue, event: dict):
        for node_name, node_update in event.items():
            if node_name == "__interrupt__":
                continue
                
            logger.info(f"[{session_id}] Node completed: {node_name}")
            
            # Extract step progress details safely
            if isinstance(node_update, dict):
                step = node_update.get("current_step", node_name)
                progress = node_update.get("progress_pct", 0)
                status = node_update.get("status", "processing")
                error = node_update.get("error")
            else:
                step = node_name
                progress = 0
                status = "processing"
                error = None
            
            # Map node updates to standard statuses if node doesn't specify
            if node_name == "specifications_analyzer_node":
                progress = 10
                step = "specs_analyzed"
            elif node_name == "schedule_parser_node":
                progress = 25
                step = "schedule_parsed"
            elif node_name == "ocr_consensus_node":
                progress = 45
                step = "ocr_completed"
            elif node_name == "cv_detector_node":
                progress = 75
                step = "cv_detector_completed"
            elif node_name == "reconciliation_node":
                progress = 90
                step = "reconciliation_completed"
            elif node_name in ["excel_writer_node", "plan_annotation_node"]:
                progress = 100
                step = "completed"
                status = "completed"

            # We removed aupdate_state here because modifying state during parallel execution 
            # (excel_writer_node and plan_annotation_node) causes InvalidUpdateError in LangGraph.
            # The progress updates will just be streamed to the frontend via the queue.

            await queue.put({
                "step": step,
                "progress": progress,
                "status": status,
                "error": error
            })

# Global session manager singleton
session_manager = SessionManager()
