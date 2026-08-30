# AI Code Review Agent

An AI-powered codebase understanding and review application that analyzes source-code repositories using **Retrieval-Augmented Generation (RAG)**, semantic search, vector embeddings, and a Large Language Model (LLM).

The application allows users to provide a GitHub repository, index its source code, ask natural-language questions about the codebase, and receive AI-generated explanations grounded in retrieved repository context.

---

## Live Application

**Frontend:**
https://ai-code-review-agent-omega.vercel.app

**Backend API:**
https://ai-code-review-agent-production-41af.up.railway.app

**GitHub Repository:**
https://github.com/mounikabopperla/ai-code-review-agent

---

## Project Overview

Understanding an unfamiliar software repository can require manually searching through many files and following code across multiple modules.

The **AI Code Review Agent** addresses this problem by combining repository ingestion, code chunking, embeddings, semantic retrieval, Qdrant vector storage, and Gemini-powered generation.

Instead of sending an entire repository directly to an LLM, the application first indexes the source code, retrieves the most relevant code context for a question, and then provides that context to the LLM.

This creates a repository-aware AI assistant capable of explaining and answering questions about the actual codebase.

---

## Features

- GitHub repository ingestion
- Repository source-code analysis
- Repository caching
- Intelligent code chunking
- Vector embedding generation
- Semantic code retrieval
- Qdrant vector database integration
- Retrieval-Augmented Generation (RAG)
- Gemini LLM integration
- Project overview generation
- Natural-language codebase questions
- Beginner explanation mode
- Intermediate explanation mode
- Expert explanation mode
- FastAPI REST backend
- React + TypeScript frontend
- Vite frontend
- Dockerized backend and frontend
- Nginx frontend serving
- Automated testing with Pytest
- GitHub Actions CI
- Production deployment using Vercel and Railway
- Environment-based API key management

---

##  How the AI Pipeline Works

### 1. Repository Ingestion

The application receives a repository path or GitHub repository URL.

The ingestion layer loads relevant source-code files while filtering files that should not be analyzed.

### 2. Code Chunking

Large source files are divided into smaller chunks so that individual sections of code can be processed efficiently.

The chunks preserve useful source-code context for later retrieval.

### 3. Embedding Generation

Code chunks are converted into numerical vector representations.

These vectors allow semantically related code sections to be located during retrieval.

### 4. Vector Storage

The generated vectors and associated metadata are stored in **Qdrant**.

The vector database provides semantic similarity search over indexed code.

### 5. Semantic Retrieval

When a user asks a question, the system searches the vector database for code chunks relevant to the question.

The retrieval layer identifies the repository context that is most useful for answering the user's question.

### 6. RAG Pipeline

The retrieved code chunks are assembled into contextual information for the language model.

This provides the LLM with information from the actual repository.

### 7. Gemini Generation

Gemini receives the user's question together with the retrieved repository context and generates a contextual explanation.

### 8. Frontend Response

The generated explanation is returned through the FastAPI backend and displayed in the React frontend.

---

##  End-to-End Workflow

```text
                    GitHub Repository
                           │
                           ▼
                 Repository Ingestion
                           │
                           ▼
                    Code Chunking
                           │
                           ▼
                 Embedding Generation
                           │
                           ▼
                  Qdrant Vector Store
                           │
                           ▼
                    Semantic Search
                           │
                    User Question
                           │
                           ▼
                    RAG Pipeline
                           │
                           ▼
                      Gemini LLM
                           │
                           ▼
                 Contextual Answer
                           │
                           ▼
                   React Frontend
```

---

## Production Architecture

```text
                         ┌──────────────────────┐
                         │     User / Browser   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Vercel Frontend    │
                         │ React + TypeScript    │
                         │        + Vite        │
                         └──────────┬───────────┘
                                    │
                              REST API
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Railway Backend    │
                         │       FastAPI        │
                         └──────────┬───────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
      Repository Ingestion     RAG Pipeline            API Layer
              │                     │
              ▼                     ▼
       Code Chunking             Qdrant
              │                     │
              ▼                     ▼
        Embeddings          Semantic Retrieval
                                    │
                                    ▼
                              Gemini LLM
                                    │
                                    ▼
                          Contextual Response
```

---

##  Example Questions

The application can be used to ask questions such as:

```text
What does this project do?
```

```text
Where is the main API entry point?
```

```text
How does repository indexing work?
```

```text
Where is authentication implemented?
```

```text
Explain the main data flow of this application.
```

```text
What is the purpose of this file?
```

```text
Explain this project in beginner mode.
```

```text
What are the main components of this repository?
```

---

## Technology Stack

### Backend

- Python
- FastAPI
- Uvicorn
- Pydantic
- Google Gemini
- Qdrant
- Vector embeddings
- Retrieval-Augmented Generation
- Pytest

### Frontend

- React
- TypeScript
- Vite
- CSS

### Infrastructure

- Vercel
- Railway
- Docker
- Docker Compose
- Nginx

### Development & CI/CD

- Git
- GitHub
- GitHub Actions
- Pytest

---

## Project Structure

```text
ai-code-review-agent/
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── backend/
│   ├── api/
│   │   ├── indexing_routes.py
│   │   ├── main.py
│   │   └── qa.py
│   │
│   ├── config/
│   │   └── settings.py
│   │
│   ├── embeddings/
│   │   └── embed_chunks.py
│   │
│   ├── ingestion/
│   │   └── chunk_code.py
│   │
│   ├── llm/
│   │   ├── formatter.py
│   │   └── generator.py
│   │
│   ├── rag/
│   │   └── pipeline.py
│   │
│   ├── retrieval/
│   │   └── search.py
│   │
│   ├── storage/
│   │   └── repository_cache.py
│   │
│   └── vector_store/
│       └── qdrant_store.py
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatBox.tsx
│   │   │   ├── InputBox.tsx
│   │   │   └── Message.tsx
│   │   │
│   │   ├── services/
│   │   │   └── api.ts
│   │   │
│   │   ├── types/
│   │   │   └── index.ts
│   │   │
│   │   ├── App.tsx
│   │   ├── App.css
│   │   ├── index.css
│   │   └── main.tsx
│   │
│   ├── package.json
│   ├── package-lock.json
│   └── vite.config.ts
│
├── ingestion/
│   ├── chunk_code.py
│   ├── embed_chunks.py
│   └── repo_loader.py
│
├── tests/
│   ├── test_chunk_code.py
│   ├── test_indexing_cache_behavior.py
│   ├── test_repo_loader.py
│   └── test_repository_cache.py
│
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
├── nginx.conf
├── pytest.ini
├── requirements.txt
└── README.md
```

---

## API Endpoints

### Health Check

```http
GET /health
```

Example response:

```json
{
  "status": "ok"
}
```

### Root

```http
GET /
```

Returns a basic API status message.

### Start Repository Indexing

```http
POST /index
```

Starts the repository indexing workflow.

### Indexing Status

```http
GET /index/status/{job_id}
```

Returns indexing status and progress for an indexing job.

### Ask a Codebase Question

```http
POST /ask
```

The endpoint accepts:

- Question
- Explanation mode
- Repository path or GitHub URL

Example request:

```json
{
  "question": "What does this project do?",
  "explanation_mode": "beginner",
  "repo_path": "https://github.com/example/repository"
}
```

### Project Overview

```http
POST /project/overview
```

Generates an overview of the indexed repository.

---

## Testing

The project includes automated tests covering repository loading, code chunking, repository caching, and indexing behavior.

Run the complete test suite from the project root:

```bash
pytest -q
```

Current verified result:

```text
26 passed
```

The complete test suite was also verified using:

```bash
python -m pytest -q
```

Result:

```text
26 passed
```

---

## Continuous Integration

GitHub Actions automatically validates the project when changes are pushed.

The CI workflow performs backend and frontend validation:

```text
Git Push
   │
   ▼
GitHub Actions
   │
   ├── Install Python dependencies
   │
   ├── Run Pytest
   │
   └── Build Frontend
           │
           └── Vite Production Build
```

This helps catch backend test failures and frontend build problems before deployment.

---

## Local Development

### 1. Clone the repository

```bash
git clone https://github.com/mounikabopperla/ai-code-review-agent.git

cd ai-code-review-agent
```

### 2. Create a Python virtual environment

```bash
python3 -m venv venv

source venv/bin/activate
```

### 3. Install backend dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a local `.env` file.

Example:

```text
GOOGLE_API_KEY=your_google_api_key
GEMINI_MODEL=your_gemini_model
```

Never commit `.env` or API keys to GitHub.

### 5. Run the backend

```bash
python -m uvicorn backend.api.main:app --reload --port 8000
```

### 6. Run the frontend

Open another terminal:

```bash
cd frontend

npm install

npm run dev
```

---

## Docker

The project contains separate Docker configurations for the backend and frontend.

Build and start the application:

```bash
docker compose up --build
```

Stop the services:

```bash
docker compose down
```

### Backend Container

The backend container runs FastAPI using Uvicorn.

### Frontend Container

The frontend is built using Vite and served using Nginx.

---

## Production Deployment

The application is deployed using separate frontend and backend services.

### Frontend

**Platform:** Vercel

```text
React + TypeScript + Vite
           │
           ▼
         Vercel
```

### Backend

**Platform:** Railway

```text
FastAPI
   │
   ├── Repository Ingestion
   ├── RAG Pipeline
   ├── Qdrant
   └── Gemini
```

### Production URLs

**Frontend:**

https://ai-code-review-agent-omega.vercel.app

**Backend API:**

https://ai-code-review-agent-production-41af.up.railway.app

---

## Security

API credentials are managed through environment variables rather than being hardcoded into application source code.

Local secrets are stored in:

```text
.env
```

The `.env` file is excluded from Git using `.gitignore`.

Production credentials are configured through deployment-platform environment variables.

API keys should never be committed to source control.

Before the final GitHub deployment, the repository was checked for exposed Gemini API key patterns.

---

## What I Learned From This Project

This project provided hands-on experience with several modern AI engineering concepts:

- Retrieval-Augmented Generation
- Semantic search
- Vector databases
- Code chunking
- Embeddings
- LLM integration
- Repository ingestion
- Caching
- FastAPI API development
- React frontend development
- TypeScript
- Docker
- Cloud deployment
- Automated testing
- GitHub Actions
- Environment-based secret management

The project also demonstrates how multiple AI application components can work together as a complete end-to-end system.

---

## Current Limitations

The current version focuses on repository-level code understanding and semantic retrieval.

Because responses depend on retrieved repository context, highly specific questions may occasionally require improved retrieval coverage or more precise source-code localization.

The system is therefore best viewed as a repository-aware code understanding assistant rather than a replacement for a full software engineering review process.

---

## Future Improvements

- Pull-request review automation
- Inline GitHub code-review comments
- Multi-repository workspaces
- Streaming LLM responses
- Authentication and user accounts
- Persistent review history
- Improved retrieval evaluation
- Code dependency graphs
- Repository architecture visualization
- More precise source-code localization
- MCP-based developer tooling
- Improved code-review reasoning
- Better repository-wide context management

---

## Project Status

**Version:** `1.0`

**Status:** Production Deployed

- Frontend: Vercel
- Backend: Railway
- Health endpoint: Working
- Gemini integration: Working
- Qdrant integration: Working
- RAG pipeline: Working
- Automated tests: **26 passing**
- GitHub Actions: Configured
- API credentials: Environment-based
- Git working tree: Clean

---

## Author

**Mounika Bopperla**

MS in Data Science
University of North Texas

**GitHub:**
https://github.com/mounikabopperla

**LinkedIn:**
https://www.linkedin.com/in/bopperla-mounika/

---

## 📄 Repository

https://github.com/mounikabopperla/ai-code-review-agent