from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.services.graph.state import CostmateState

from app.services.agents.layer1_schedule.schedule_parser_node import schedule_parser_node
from app.services.agents.layer2_vision.ocr_consensus_node import ocr_consensus_node
from app.services.agents.layer2_vision.cv_detector_node import cv_detector_node

from app.services.agents.layer3_human.reconciliation_node import reconciliation_node
from app.services.agents.layer3_human.interrupt_node import interrupt_node

from app.services.agents.layer5_output.excel_writer_node import excel_writer_node
from app.services.agents.layer5_output.plan_annotation_node import plan_annotation_node

def build_graph():
    builder = StateGraph(CostmateState)
    
    # 1. Add all nodes
    builder.add_node("schedule_parser_node", schedule_parser_node)
    builder.add_node("ocr_consensus_node", ocr_consensus_node)
    builder.add_node("cv_detector_node", cv_detector_node)
    
    builder.add_node("reconciliation_node", reconciliation_node)
    builder.add_node("interrupt_node", interrupt_node)
    
    builder.add_node("excel_writer_node", excel_writer_node)
    builder.add_node("plan_annotation_node", plan_annotation_node)
    
    # 2. Add edges
    # START -> Parallel Extraction Tracks (A, B, C)
    builder.add_edge(START, "schedule_parser_node")
    builder.add_edge(START, "ocr_consensus_node")
    builder.add_edge(START, "cv_detector_node")
    
    # Parallel Tracks -> Reconciliation Join
    builder.add_edge("schedule_parser_node", "reconciliation_node")
    builder.add_edge("ocr_consensus_node", "reconciliation_node")
    builder.add_edge("cv_detector_node", "reconciliation_node")
    
    # Reconciliation -> Human Review Interrupt
    builder.add_edge("reconciliation_node", "interrupt_node")
    
    # Human Review -> Parallel Final Exports
    builder.add_edge("interrupt_node", "excel_writer_node")
    builder.add_edge("interrupt_node", "plan_annotation_node")
    
    # Final Exports -> END
    builder.add_edge("excel_writer_node", END)
    builder.add_edge("plan_annotation_node", END)
    
    # Compile graph with memory checkpointing
    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory, interrupt_before=["interrupt_node"])
    
    return graph

# Export a compiled graph instance
costmate_graph = build_graph()
