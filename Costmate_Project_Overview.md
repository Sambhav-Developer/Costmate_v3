# Costmate: AI-Powered Civil Estimation Platform

## Overview
Costmate is a cutting-edge web application designed to automate and streamline the process of civil engineering and construction estimation. By leveraging an advanced Agentic AI Swarm, Costmate can analyze architectural floor plans (PDFs or images), intelligently extract structural dimensions and elements, and automatically generate a comprehensive Bill of Quantities (BOQ) and cost estimate.

## Core Features
1. **AI Vision Parsing:** Users can upload architectural drawings. The system uses advanced Vision Language Models (VLMs) via the OpenRouter API to scan the blueprints, extracting room dimensions, beams, columns, and footings.
2. **Interactive Human-in-the-Loop QA:** Before running the final calculations, the extracted data is presented in an intuitive, glassmorphic UI. Users can review, edit, or add missing parameters manually or by chatting with the integrated "AI Swarm Copilot."
3. **Automated BOQ Generation:** Based on the verified parameters and selected rate schedules (e.g., CPWD), the backend calculates precise quantities for civil materials (concrete, excavation, tiles, plaster) and steel reinforcement.
4. **Excel Export:** The final output is automatically formatted into a professional, multi-sheet Excel document, which users can preview directly in the browser using an integrated spreadsheet viewer or download for external use.

## Technology Stack
- **Frontend:** Built with Next.js (React) and Tailwind CSS. The UI features a modern, dark-mode glassmorphism aesthetic with smooth animations, interactive schedule tables, and a real-time AI copilot chat interface. It utilizes Wijmo FlexSheet for in-browser Excel rendering.
- **Backend:** Powered by Python and FastAPI. It handles secure file uploads, PDF processing (via PyMuPDF), and database interactions.
- **AI Engine:** The core intelligence is orchestrated using **LangGraph**. It creates a multi-step pipeline (OCR, Vision Agents, Prefill QA, Validation, Calculation, and Excel Writer). The system relies on the **OpenRouter API** (running massive models like `qwen/qwen3.5-397b-a17b`) for deep reasoning and multimodal analysis.
- **Database:** PostgreSQL is used to persist user sessions, draft states, and graph checkpoints, ensuring that long-running estimations can be paused, resumed, and hot-reloaded without data loss.

## Workflow
1. **Upload:** User creates a "New Project" and uploads a floor plan.
2. **Analysis:** The AI pipeline runs in the background, breaking the PDF into images and analyzing them.
3. **Review:** The system pauses at a "Human Gate." The UI populates with draft schedules (Columns, Beams, Footings, Rooms).
4. **Refine:** The user modifies the data manually or asks the AI Copilot (e.g., "Change all B1 beams to 10").
5. **Recalculate:** The user clicks "Recalculate Estimate." The backend finalizes the state, runs civil/steel calculations, and generates the BOQ.
6. **Result:** The user reviews the generated Excel sheet directly on the platform and downloads it.
