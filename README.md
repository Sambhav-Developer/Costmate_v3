<div align="center">
  <h1>🏗️ Costmate</h1>
  <p><strong>Next-Generation AI Civil Work Estimation & Quantization Engine</strong></p>
  <p>Costmate is a powerful, AI-driven platform that revolutionizes the way construction estimates are created. By leveraging a Multi-Agent Vision Swarm, it autonomously reads 2D architectural floor plans, extracts spatial dimensions, identifies structural elements, and instantly generates comprehensive Bills of Quantities (BOQ) and Civil Quantization reports.</p>
</div>

---

## 🚀 Key Features

*   **Multi-Agent AI Swarm:** Utilizes a highly concurrent LangGraph-based AI architecture (OCR Node, Dimension Extractor, Element Detector, Floor Plan Reader) to process complex floor plans in parallel.
*   **Computer Vision OCR:** Deep integration with OpenRouter vision models (`OpenRouter Vision Model`) to accurately detect rooms, dimensions, doors, windows, and structural columns directly from uploaded PDFs and images.
*   **Conversational AI Copilot:** A built-in LLM chat assistant that understands the project context. You can use natural language to execute CRUD operations (e.g., *"Change all toilet doors on the terrace to UPVC"*), and the backend instantly deep-merges the updates.
*   **Interactive Bounding Boxes:** Real-time visual verification. Hovering over a data row highlights the exact coordinate boundaries on the raw blueprint, ensuring total transparency and trust.
*   **Intelligent Layout Replication:** Front-end setup wizard allows engineers to map identical typical floors (e.g., copy First Floor specs to Second & Third) without redundant AI processing, seamlessly managed by the backend intake parser.
*   **Instant BOQ Generation:** Automatically deduces concrete volumes, excavation depths, plastering schedules, and material finishes from the extracted footprints and exports them to industry-standard formats.

## 🛠️ Technology Stack

### Backend
*   **Framework:** FastAPI (Python 3.10+)
*   **AI / Orchestration:** LangChain, LangGraph (Multi-Agent framework)
*   **LLM Provider:** OpenRouter (Qwen & Llama Vision Models)
*   **Database:** PostgreSQL with SQLAlchemy & Alembic (Asyncpg)
*   **Storage:** Cloudinary (Dynamic URL image transformations to optimize AI ingestion)

### Frontend
*   **Framework:** React / Next.js
*   **Styling:** Tailwind CSS / Custom Vanilla CSS (Modern, dark-mode, glassmorphism aesthetics)
*   **State Management:** React Hooks
*   **API Client:** Axios / Fetch

## ⚙️ Architecture & Data Flow

1.  **Ingestion:** User uploads a PDF/PNG floor plan via the Setup Wizard. The image is instantly uploaded to Cloudinary, and a `quick-scan` detects boundaries.
2.  **Swarm Orchestration:** Upon finalization, the backend triggers the `CostmateState` Graph.
3.  **Parallel Execution:** The Dimension Extractor, Element Detector, and Floor Plan Reader analyze the Cloudinary URLs concurrently, leveraging GPU-accelerated endpoints via OpenRouter.
4.  **Consolidation:** The `prefill_qa_node` meticulously maps the AI-extracted data against the user-defined `intake_floors` configuration, filtering out duplicates and resolving missing floors via intelligent inheritance.
5.  **Human-in-the-Loop:** The engineer reviews the extracted parameters, edits values via the UI or the Conversational Copilot, and finalizes the BOQ.

## 💻 Local Development Setup

### Prerequisites
*   Python 3.10+
*   Node.js 18+
*   PostgreSQL
*   OpenRouter API Key
*   Cloudinary API Credentials

### Backend Setup
```bash
# Navigate to the backend directory
cd Backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up your environment variables
# Create a .env file and add: DATABASE_URL, OPENROUTER_API_KEY, CLOUDINARY_URL, etc.

# Initialize the database schema
alembic upgrade head

# Run the development server
uvicorn app.main:app --reload
```

### Frontend Setup
```bash
# Navigate to the frontend directory
cd Frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```
*The frontend will typically run on `http://localhost:3000` and communicate with the FastAPI backend on `http://localhost:8000`.*

## 🐛 Troubleshooting
*   **OpenRouter CUDA OOM (Out of Memory):** Costmate uses dynamic Cloudinary URL transformations (e.g., `c_limit,w_2000`) before sending images to OpenRouter. If you change storage providers, ensure you compress high-resolution architectural PDFs before sending them to the Vision LLM to prevent remote VRAM crashes.
*   **Missing Floors in Final Output:** Ensure you do not skip naming your floors in the Setup Wizard. The `interrupt_node.py` heavily relies on the `intake_data` to properly sequence and assign rooms.

---
*Built for the future of construction engineering.*
