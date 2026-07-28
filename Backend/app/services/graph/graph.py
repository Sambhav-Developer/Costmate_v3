from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.services.graph.state import CostmateState
from app.services.agents.layer2_vision.ocr_node import ocr_node
from app.services.agents.layer2_vision.floor_plan_reader import floor_plan_reader_node
from app.services.agents.layer2_vision.dimension_extractor import dimension_extractor_node
from app.services.agents.layer2_vision.element_detector import element_detector_node
from app.services.agents.layer3_human.interrupt_node import prefill_qa_node, interrupt_node
from app.services.agents.layer4_calculation.p1_civil_quantities import civil_quantities_node
from app.services.agents.layer5_output.validator import validator_node
from app.services.agents.layer5_output.excel_writer import excel_writer_node

def build_graph():
    # Initialize state graph
    builder = StateGraph(CostmateState)
    
    # 1. Add all nodes
    builder.add_node("ocr_node", ocr_node)
    
    builder.add_node("floor_plan_reader_node", floor_plan_reader_node)
    builder.add_node("dimension_extractor_node", dimension_extractor_node)
    builder.add_node("element_detector_node", element_detector_node)
    
    builder.add_node("prefill_qa_node", prefill_qa_node)
    builder.add_node("interrupt_node", interrupt_node)
    
    builder.add_node("civil_quantities_node", civil_quantities_node)
    builder.add_node("validator_node", validator_node)
    builder.add_node("excel_writer_node", excel_writer_node)
    
    # 2. Add edges
    # START -> OCR
    builder.add_edge(START, "ocr_node")
    
    # OCR -> parallel Vision agents (fan-out)
    builder.add_edge("ocr_node", "floor_plan_reader_node")
    builder.add_edge("ocr_node", "dimension_extractor_node")
    builder.add_edge("ocr_node", "element_detector_node")
    
    # Vision agents -> Prefill QA Node (fan-in / join)
    builder.add_edge("floor_plan_reader_node", "prefill_qa_node")
    builder.add_edge("dimension_extractor_node", "prefill_qa_node")
    builder.add_edge("element_detector_node", "prefill_qa_node")
    
    # Prefill QA Node -> QA Interrupt
    builder.add_edge("prefill_qa_node", "interrupt_node")
    
    # QA Interrupt -> civil quantities calculation
    builder.add_edge("interrupt_node", "civil_quantities_node")
    
    # Quantities -> Validation
    builder.add_edge("civil_quantities_node", "validator_node")
    
    # Validation -> Excel Writer
    builder.add_edge("validator_node", "excel_writer_node")
    
    # Excel Writer -> END
    builder.add_edge("excel_writer_node", END)
    
    # Compile graph with memory checkpointing for interrupts
    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory, interrupt_before=["interrupt_node"])
    
    return graph

# Export a compiled graph instance
costmate_graph = build_graph()
