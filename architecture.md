# Costmate V3 Agentic Architecture

Costmate is built on a structured, layered multi-agent swarm orchestrated by **LangGraph**. The system processes architectural blueprints, specifications, and schedules to produce a complete Bill of Quantities (BOQ).

---

## 🏗️ Layer-Wise Architecture

```mermaid
graph TD
    %% Define Layers
    subgraph Layer_1["Layer 1: Ingestion, Schedules & Specs"]
        SA[Specifications Analyzer Node]
        SP[Schedule Parser Node]
    end

    subgraph Layer_2["Layer 2: Extraction Tracks"]
        OC[OCR Consensus Node]
        CV[CV Detector Node]
    end

    subgraph Layer_3["Layer 3: Reconciliation & Human Gate"]
        RE[Reconciliation Node]
        IN[Interrupt Node <br/>PAUSED FOR QA]
    end

    subgraph Layer_5["Layer 5: Output Generation"]
        EW[Excel Writer Node]
        PA[Plan Annotation Node]
    end

    %% Execution Flow
    START --> SA
    SA --> SP
    SP --> OC
    OC --> CV
    CV --> RE
    RE --> IN
    
    %% Human Gate Resume
    IN -->|Verified QA Form| EW
    IN -->|Verified QA Form| PA
    EW --> END
    PA --> END
```

---

## 🤖 Layer & Agent Responsibilities

| Layer | Agent / Node | Input | Target / Output | Role & Responsibility | Why We Use It |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Layer 1** | **Specifications Analyzer** | Raw `.docx`/`.txt` specification files | `specifications_insights` (JSON) | Extracts hardware exclusions (e.g. Aluminium exclusions), materials, and project constraints. | Filters out materials not in the estimator's scope to prevent wrong pricing. |
| **Layer 1** | **Schedule Parser** | Uploaded Schedule sheets (Image/PDF) | `schedule_data` (JSON) | Extracts door/window schedule tables (sizes, counts, frames) using dual-pass Qwen-72B VLM. | Digitizes structural schedule parameters into a canonical format. |
| **Layer 2** | **OCR Consensus** | Uploaded Plan drawings (PDF/Image) | `ocr_results` (Text list) | Multi-pass text parser to extract text labels and room locations from plans. | Ensures room tags and numbers are extracted with high character accuracy. |
| **Layer 2** | **CV Detector** | Uploaded Plan drawings (PDF/Image) + `schedule_data` | `cv_results` (JSON list of matches) | Matches marks (e.g. D1, W2) to layouts, cropping images and classifying swing directions. | Physically locates door/window icons on drawings and detects opening swing modes. |
| **Layer 3** | **Reconciliation Node** | Outputs from Layers 1 & 2 | `qa_prefilled` (JSON) + `unresolved_queue` | Merges OCR text extraction and CV detection results; flags mismatching doors for human check. | Combines visual/textual data and structures the review dashboard. |
| **Layer 3** | **Interrupt Node** | Prefilled QA schema | User input updates via UI | Halts the LangGraph run state machine until the user validates the parameters. | Acts as the **Human Gate** to ensure 100% precision before final calculations. |
| **Layer 5** | **Excel Writer** | Verified Q&A Form | Formatted `.xlsx` BOQ | Generates Estimation and Raw schedules, applying correct column orders. | Builds the final customer-ready Microsoft Excel takeoff sheet. |
| **Layer 5** | **Plan Annotation** | Verified Q&A Form + Plans | Annotated plan drawings | Overlays green/red pins on plans pointing to located door/window openings. | Provides visual validation of all detected items directly on the layout drawings. |

---

## 🔄 Flow of Execution

```mermaid
sequenceDiagram
    autonumber
    actor User as Estimator (Frontend)
    participant API as FastAPI Backend
    participant Graph as LangGraph Orchestrator
    participant VLM as Qwen VLM API

    User->>API: 1. Upload Plans, Schedules, & Specs (Setup Wizard)
    API->>Graph: 2. Initialize Session State
    
    activate Graph
    Graph->>VLM: 3. specifications_analyzer_node
    VLM-->>Graph: Return exclusions & notes
    
    Graph->>VLM: 4. schedule_parser_node (Dual-pass)
    VLM-->>Graph: Return structured schedule registry
    
    Graph->>VLM: 5. ocr_consensus_node
    VLM-->>Graph: Return plan text labels
    
    Graph->>VLM: 6. cv_detector_node (Programmatic + LLM crops)
    VLM-->>Graph: Return drawing matches & locations per plan page
    
    Graph->>Graph: 7. reconciliation_node (Aligns plan marks to floors)
    Graph->>API: 8. Pause state at interrupt_node (50% progress)
    deactivate Graph
    
    API-->>User: 9. Display prefilled tables on Parameters Tab
    
    User->>User: 10. (Optional) Drag columns, rename, or fix room values
    User->>API: 11. Click "Verify & Run Estimate"
    
    activate Graph
    API->>Graph: 12. Resume graph with User's verified Q&A Form
    
    Graph->>API: 13. excel_writer_node (Generate XLSX sheets)
    Graph->>API: 14. plan_annotation_node (Overlays target circles on drawings)
    
    Graph-->>API: 15. Set status to completed (100% progress)
    deactivate Graph
    
    API-->>User: 16. Unlock Final BOQ spreadsheets & Annotated PDFs for download
```
