# Costmate Pipeline Architecture

Based on the provided architecture diagram, this document outlines the core data processing pipeline for Costmate.

## Flow Diagram

```text
[ Upload PDF (Schedules + floor plans) ]
       │
       ├──► [ Schedule parser ] ───────────────────────────┐
       │     (Native + OCR fallback)                       │
       │                                                   │
       ├──► [ OCR Swarm (OCR1 + OCR2) ] ──┐                │
       │     (Diff temps + prompts)       │                │
       │                                  ▼                │
       │                        [ >=80% match? ]           │
       │                        (OCR3 tiebreaker)          │
       │                                  │                │
       │                     ┌─(Match)────┴──(Mismatch)─┐  │
       │                     │                          │  │
       └──► [ Computer Vision ]                         │  │
             (OpenCV / YOLO) ───────────────────────────┤  │
                                                        ▼  │
                                                [ Unresolved ]
                                                (Human review)
                                                        │  │
                                ┌───────────────────────┴──┘
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
[ Excel Agent ]                                [ Plan Annotation ]
(Combines columns)                             (Color-codes marks)
        │                                               │
        ▼                                               ▼
[ Downloadable Excel ]                         [ Annotated PDF Plan ]
```

## Description of the Pipeline

1. **Ingestion (`Upload PDF`)**: The system accepts a PDF containing both schedule tables and architectural floor plans.
2. **Parallel Processing**:
   - **Schedule Parser**: Uses native parsing with an OCR fallback to extract structured data from tables.
   - **OCR Swarm (`OCR1 + OCR2`)**: Two distinct OCR agents run with different temperatures and prompts to read the marks/tags on the floor plans.
   - **Computer Vision (`OpenCV / YOLO / SAM`)**: Detects the bounding boxes and visual boundaries of marks on the plans.
3. **Consensus & Resolution (`>=80% match?`)**: 
   - The outputs of the two primary OCR agents are compared. If they disagree, a third agent (`OCR3`) is triggered for a 2-of-3 tie-breaker vote.
   - If consensus still cannot be reached, or if the CV system detects anomalies, the data is pushed to an **Unresolved (Human Review)** gate.
4. **Output Generation**:
   - Both the verified data and the human-reviewed data flow into downstream generation agents.
   - **Excel Agent**: Combines all the matched schedule columns into a final output table.
   - **Plan Annotation**: Takes the verified marks and color-codes/highlights them directly onto the floor plan.
5. **Final Deliverables**:
   - A downloadable **Excel file** (spreadsheet).
   - A downloadable **Highlighted plan** (annotated PDF).
