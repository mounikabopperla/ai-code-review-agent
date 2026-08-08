# AI Code Review Agent

An AI-powered code review system that ingests source-code repositories, breaks code into meaningful chunks, generates embeddings, stores them in a vector database, retrieves relevant context, and uses a Large Language Model (LLM) to generate contextual code-review responses.

The project combines **Retrieval-Augmented Generation (RAG)**, semantic code search, FastAPI, Qdrant, React, Docker, automated testing, and GitHub Actions CI.

---

## 🚀 Features

- Repository source-code ingestion
- Intelligent code chunking
- Embedding generation
- Semantic code retrieval
- Qdrant vector database integration
- Retrieval-Augmented Generation (RAG)
- LLM-powered code analysis
- FastAPI REST backend
- React + TypeScript frontend
- Dockerized backend and frontend
- Automated Python testing with Pytest
- GitHub Actions CI for backend tests and frontend builds

---

## 🏗️ Architecture

```text
                ┌─────────────────────┐
                │   Source Repository │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │ Repository Loader   │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │   Code Chunking     │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │     Embeddings      │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │       Qdrant        │
                │   Vector Database   │
                └──────────┬──────────┘
                           │
                           ▼
User Question ─────► Semantic Retrieval
                           │
                           ▼
                ┌─────────────────────┐
                │    RAG Pipeline     │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │        LLM          │
                └──────────┬──────────┘
                           │
                           ▼
                    Code Review
```

---

## 🔄 How It Works

### 1. Repository Ingestion

The ingestion layer loads source-code files from a repository while filtering files that should not be analyzed.

### 2. Code Chunking

Large source files are divided into smaller chunks so they can be embedded and retrieved efficiently.

### 3. Embeddings

Code chunks are converted into numerical vector representations.

### 4. Vector Storage

The generated embeddings are stored in **Qdrant**, allowing semantic similarity searches across the codebase.

### 5. Retrieval

When a user asks a question, the system searches the vector database for the code chunks most relevant to the query.

### 6. RAG Pipeline

The retrieved code is supplied as contextual information to the language model.

### 7. AI Code Review

The LLM analyzes the retrieved context and generates a code-review response grounded in the repository.

---

## 🛠️ Tech Stack

### Backend

- Python
- FastAPI
- Pytest
- Qdrant
- Vector embeddings
- Retrieval-Augmented Generation (RAG)
- LLM integration

### Frontend

- React
- TypeScript
- Vite
- CSS

### DevOps

- Docker
- Docker Compose
- Nginx
- Git
- GitHub
- GitHub Actions

---

## 📁 Project Structure

```text
ai-code-review-agent/
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── backend/
│   ├── api/
│   ├── config/
│   ├── embeddings/
│   ├── ingestion/
│   ├── llm/
│   ├── rag/
│   ├── retrieval/
│   └── vector_store/
│
├── frontend/
│   └── src/
│       ├── components/
│       ├── services/
│       └── types/
│
├── ingestion/
│   ├── chunk_code.py
│   ├── embed_chunks.py
│   └── repo_loader.py
│
├── tests/
│   ├── test_chunk_code.py
│   └── test_repo_loader.py
│
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
├── nginx.conf
├── pytest.ini
└── requirements.txt
```

---

## 🧪 Testing

The backend contains automated tests for repository ingestion and code chunking.

Run the test suite from the project root:

```bash
pytest -q
```

Current test suite:

```text
18 passed
```

---

## 💻 Frontend Build

To verify the production frontend build:

```bash
cd frontend
npm install
npm run build
```

---

## ⚙️ Local Development

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

### 4. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 5. Run backend tests

```bash
pytest -q
```

---

## 🐳 Docker

The project contains separate Docker configurations for the backend and frontend and can be orchestrated using Docker Compose.

```bash
docker compose up --build
```

To stop the services:

```bash
docker compose down
```

---

## 🔁 Continuous Integration

GitHub Actions automatically validates the project whenever code is pushed.

The CI workflow performs two independent checks:

```text
Backend Tests
    ↓
Install Python dependencies
    ↓
Run Pytest

Frontend Build
    ↓
Install Node dependencies
    ↓
Compile TypeScript
    ↓
Create Vite production build
```

Both pipelines must succeed before a change is considered build-safe.

---

## 🎯 Project Goal

The goal of this project is to demonstrate how **semantic search and Retrieval-Augmented Generation can be applied to software engineering workflows**.

Instead of asking an LLM to review code without repository context, the system retrieves relevant source-code sections first and provides them to the model, allowing responses to be grounded in the actual codebase.

---

## 🔮 Future Improvements

- GitHub repository URL ingestion
- Pull-request review automation
- Inline code-review comments
- Multi-repository indexing
- Streaming LLM responses
- Authentication
- Persistent review history
- Improved retrieval evaluation
- Production cloud deployment

---

## 👩‍💻 Author

**Mounika Bopperla**

MS in Data Science  
University of North Texas

GitHub: [mounikabopperla](https://github.com/mounikabopperla)

LinkedIn: [Mounika Bopperla](https://www.linkedin.com/in/bopperla-mounika/)

---

## 📌 Status

🟢 Active Development

Backend automated tests: **18 passing**

GitHub Actions:

- ✅ Backend Tests
- ✅ Frontend Build