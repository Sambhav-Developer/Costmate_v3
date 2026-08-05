# Costmate: AI-Powered Civil Estimation Platform

Welcome to the **Costmate** repository! Costmate is a cutting-edge web application designed to automate and streamline the process of civil engineering and construction estimation. 

By leveraging an advanced Agentic AI Swarm, Costmate can analyze architectural floor plans (PDFs or images), intelligently extract structural dimensions and elements, and automatically generate a comprehensive Bill of Quantities (BOQ) and cost estimate.

## 🚀 Key Features

- **Automated Blueprint Analysis**: Upload PDF schedules and floor plans. Our multi-agent AI pipeline (powered by OpenRouter VLMs) scans the blueprints to extract room dimensions, beams, columns, doors, windows, and footings.
- **Intelligent Schedule Parsing**: The backend dynamically parses complex, multi-page schedules (e.g., Door & Window schedules) using a unified, dynamic Pydantic extraction schema.
- **Human-in-the-Loop QA**: A modern, glassmorphic UI presents the extracted data to the user before final calculations. A dedicated `ReviewQueueModal` flags unresolved items (like OCR consensus failures) for human verification.
- **AI Swarm Copilot**: Interact directly with your project data using an integrated AI chat sidebar. Instruct the copilot to modify dimensions or add missing parameters seamlessly.
- **Dynamic Excel Export**: The finalized data is compiled into a professional, multi-sheet Excel BOQ. Users can preview this spreadsheet directly in the browser (via Wijmo FlexSheet) and download the `.xlsx` file.
- **Plan Annotation**: The system automatically generates and provides a downloadable version of the original floor plan, with all detected marks (like doors and windows) color-coded and highlighted.

## 🏗️ Architecture & Pipeline

Costmate uses a sophisticated orchestration engine using **LangGraph**. The workflow relies on swarm consensus to guarantee high accuracy.

**For a detailed look at the core AI extraction and consensus pipeline, please view:**
👉 [Pipeline Architecture Diagram](pipeline_architecture.md)

### Tech Stack

#### Frontend
- **Framework:** Next.js (React)
- **Styling:** Tailwind CSS (featuring premium dark-mode aesthetics and glassmorphism)
- **Key Components:** Interactive `TabEditor` (for schedules), `ReviewQueueModal` (for human QA), and a real-time `CopilotPanel`.

#### Backend
- **Framework:** Python / FastAPI
- **Database:** PostgreSQL (for saving sessions, drafts, and LangGraph checkpoints)
- **AI Orchestration:** LangGraph + OpenRouter API (using massive reasoning models)
- **Processing:** PyMuPDF for document ingestion, Pandas for Excel generation.

## 🛠️ Getting Started

### Prerequisites
- Node.js (v18+)
- Python 3.10+
- PostgreSQL
- OpenRouter API Key

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/khushalbairariyasam/costmate_v3.git
   cd costmate_v3
   ```

2. **Setup the Backend:**
   ```bash
   cd Backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
   *Create a `.env` file in the Backend directory and add your `OPENROUTER_API_KEY` and `DATABASE_URL`.*
   ```bash
   uvicorn app.main:app --reload
   ```

3. **Setup the Frontend:**
   ```bash
   cd ../Frontend
   npm install
   npm run dev
   ```

4. **Open the Application:**
   Navigate to `http://localhost:3000` in your browser.

## 🤝 Contributing
This project is actively being developed. If you encounter bugs, especially related to the AI parser schemas or the Review Queue, please open an issue!

## 📄 License
Costmate is proprietary software. All rights reserved.
