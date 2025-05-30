# n8n Workflow Template Manager

## Overview

The n8n Workflow Template Manager is a Python-based application designed to help you manage, search, and utilize n8n workflow templates. It supports local storage of templates, fetching community templates from n8n.io, and syncing templates from your personal GitHub repositories. It provides a simple web interface and a robust API to search and import these templates into your n8n instance.

This project aims to provide a centralized place for n8n users to discover and reuse workflow patterns, and for AI agents (like RAG systems) to access workflow data for contextual understanding.

Key components include:
*   **Database:** Supports PostgreSQL (preferred) or SQLite for storing template metadata and JSON.
*   **Whoosh Search Engine:** For fast full-text search capabilities.
*   **FastAPI Backend:** Provides API endpoints for programmatic access.
*   **Simple Web UI:** For easy searching and importing of templates.
*   **GitHub Sync Service:** To import and keep your personal n8n templates updated.

## Features

*   **Local Template Parsing:** Ingests n8n workflow JSON files from a local directory structure.
*   **Online Template Fetching:** Downloads and stores the latest community templates from the n8n.io API.
*   **GitHub Personal Template Syncing:** Clones/pulls a user-defined GitHub repository, scans for n8n workflow JSON files, processes them, and adds/updates them in the database and search index.
*   **Database Support:** PostgreSQL is the preferred database, with SQLite as a fallback.
*   **Environment Configuration:** Uses a `.env` file for easy configuration of database connections, API keys, and application settings.
*   **Categorization & Tagging:** Organizes templates by category (derived from source or keywords) and tags. GitHub-sourced templates are tagged with "github" and can be categorized based on their repository path.
*   **Full-Text Search:** Allows searching through template names, descriptions, node types, and tags.
*   **RESTful API:** Exposes endpoints for listing, searching, retrieving template details (including full JSON), and triggering GitHub syncs.
*   **Web Interface:** A user-friendly UI to browse, search, and import templates into an n8n instance.
*   **Database Backup Utility:** A simple script to back up the SQLite database (if used).
*   **RAG Enablement:** The API can be used by external AI agents or RAG (Retrieval Augmented Generation) systems to fetch workflow data for contextual information.

## Project Structure

```
n8n_template_manager/
├── app/                     # Main application code
│   ├── api/                 # FastAPI endpoints, utils
│   ├── db/                  # Database setup (PostgreSQL, SQLite)
│   ├── models/              # SQLAlchemy and Pydantic models
│   ├── services/            # Business logic (parsing, indexing, fetching, GitHub sync)
│   └── static/              # Frontend HTML, CSS, JS
├── db_backups/              # Default directory for SQLite database backups
├── scripts/                 # Utility scripts (e.g., backup_db.py)
├── whoosh_index/            # Whoosh search index files
├── workflows/               # (Optional) Default local directory for n8n JSON files to be parsed
│   └── n8n-templates-sorted/ # Example subdirectory structure for local parsing
├── .env.example             # Example environment file for configuration
├── main.py                  # Main FastAPI application entry point
├── requirements.txt         # Python dependencies
├── Dockerfile               # Dockerfile for building the application image
└── README.md                # This file
```
**Note:** The `Dockerfile` and `.dockerignore` for this application are located within the `n8n_template_manager/` directory. A root level `docker-compose.yml` and `.env` are also provided for multi-service orchestration.

## Setup and Installation

**Prerequisites:**
*   Python 3.8 or newer.
*   `pip` for installing Python packages.
*   PostgreSQL server (recommended) or ensure SQLite build tools are available.
*   Git (for GitHub Personal Template Syncing).

**Steps:**

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url> # Replace with the actual URL
    cd n8n_template_manager
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    This installs all necessary packages, including `psycopg2-binary` for PostgreSQL and `GitPython` for GitHub sync.

4.  **Configure Environment Variables:**
    Create a `.env` file in the `n8n_template_manager/` directory by copying from `.env.example`:
    ```bash
    cp .env.example .env
    ```
    Edit the `.env` file with your specific settings. See the "Environment Variables" section below for details on each variable.

## Database Configuration

The application supports both PostgreSQL and SQLite. PostgreSQL is recommended for production or robust development.

*   **PostgreSQL (Preferred):**
    To use PostgreSQL, set the `DATABASE_URL_POSTGRES` environment variable in your `n8n_template_manager/.env` file.
    Example:
    ```env
    DATABASE_URL_POSTGRES=postgresql://user:password@host:port/dbname
    ```
    The application will use this connection if the variable is set. Ensure your PostgreSQL server is running and accessible.

*   **SQLite (Fallback):**
    If `DATABASE_URL_POSTGRES` is not set, the application will default to using SQLite. The SQLite database file path can be configured with `DATABASE_URL_SQLITE`.
    Example:
    ```env
    DATABASE_URL_SQLITE=sqlite:///./n8n_templates.db
    ```
    A new SQLite file (`n8n_templates.db` by default) will be created in the `n8n_template_manager` directory if it doesn't exist.

## Environment Variables

Create a `.env` file in the `n8n_template_manager/` directory. This file is used to configure the application.

*   **`APP_HOST`**: Host address for the FastAPI application. Default: `0.0.0.0`.
*   **`APP_PORT`**: Port for the FastAPI application. Default: `8000`.
*   **`LOG_LEVEL`**: Logging level (e.g., `INFO`, `DEBUG`, `WARNING`). Default: `INFO`.
*   **`DATABASE_URL_SQLITE`**: Connection string for SQLite. Example: `sqlite:///./n8n_templates.db`. Used if `DATABASE_URL_POSTGRES` is not set.
*   **`DATABASE_URL_POSTGRES`**: Connection string for PostgreSQL. Example: `postgresql://user:password@host:port/dbname`. If set, this will be used instead of SQLite.
*   **`GITHUB_REPO_URL_PERSONAL_TEMPLATES`**: HTTPS URL of your personal GitHub repository containing n8n workflow JSON files for syncing. Example: `https://github.com/yourusername/my-n8n-workflows.git`.
*   **`GITHUB_ACCESS_TOKEN`**: Your GitHub Personal Access Token (PAT). Currently included for future use (e.g., accessing private repositories that require a token). The current GitHub fetcher primarily relies on public repo access or SSH keys configured in the environment where it runs.

## Running the Application

### 1. Initial Data Ingestion

Populate the database with workflow templates:

*   **From Local Files:** Place your n8n JSON files (e.g., in `workflows/n8n-templates-sorted/Category/workflow.json`) and run:
    ```bash
    python app/services/parser_indexer.py
    ```
    (Run from `n8n_template_manager/` directory).
*   **Fetch Templates from n8n.io:**
    ```bash
    python app/services/online_template_fetcher.py
    ```
    (Run from `n8n_template_manager/` directory).
*   **Sync from Your GitHub Repository:** See "GitHub Personal Template Syncing" section.

### 2. Starting the FastAPI Server

Once dependencies are installed and `.env` is configured, start the server from the `n8n_template_manager/` directory:
```bash
python main.py
```
The server will typically start on `http://<APP_HOST>:<APP_PORT>`.

## GitHub Personal Template Syncing

This feature allows you to connect a personal GitHub repository containing your n8n workflow JSON files. The application will clone/pull this repository, scan for `.json` files, and add or update them in the template manager's database and search index.

**Configuration:**

1.  **Set Environment Variable:**
    In your `n8n_template_manager/.env` file, set the `GITHUB_REPO_URL_PERSONAL_TEMPLATES` variable:
    ```env
    GITHUB_REPO_URL_PERSONAL_TEMPLATES=https://github.com/yourusername/your-n8n-templates.git
    ```
    Replace the URL with the HTTPS clone URL of your public repository. For private repositories, ensure the environment where the manager runs has appropriate SSH key access if using SSH URLs, or embed a PAT in the HTTPS URL (less secure, ensure `.env` is protected).

**Triggering Synchronization:**

*   Send a POST request to the `/api/v1/templates/sync_github` endpoint.
    ```bash
    curl -X POST http://localhost:8000/api/v1/templates/sync_github
    ```
    (Replace `localhost:8000` with your actual `APP_HOST` and `APP_PORT` if different).
*   The sync process runs in the background. Check application logs for details.

**Workflow Processing Details:**

*   **Identification:** Templates are uniquely identified in the database by their `source_path` (e.g., `github://your.repo.com/path/to/workflow.json`).
*   **Primary Key (`id`):**
    *   For *new* GitHub templates: The system attempts to use an `id` field from the workflow's JSON content (or the filename if no `id` field exists). If this ID is an integer and not already used as a database primary key by *any* other template, it's used. Otherwise, the database auto-generates a new primary key.
    *   For *updates* to existing GitHub templates (based on `source_path`): The existing database primary key is preserved.
*   **Updates:** If a template with the same `source_path` exists, its content is compared. If different, the existing record is updated (and its old search index entry is removed before re-indexing). Identical templates are skipped.
*   **Categorization:** Categories are derived from the directory structure within your GitHub repository (e.g., a file at `MyWorkflows/Automations/my_flow.json` becomes category "MyWorkflows/Automations").
*   **Tags:** Automatically tagged with "github". Additional tags can be derived from the category path and filename.
*   **Indexing:** New and updated workflows are automatically indexed by Whoosh.

## Building and Running with Docker (Standalone `n8n_template_manager`)

This section refers to running the `n8n_template_manager` as a standalone Docker container. For running it as part of a larger setup with n8n and PostgreSQL, see the root `docker-compose.yml` and its associated `.env` file.

*   **Build the Docker Image:**
    From the repository root, run:
    ```bash
    docker build -f ./n8n_template_manager/Dockerfile . -t n8n-template-manager-app
    ```
    This command uses the repository root as the build context. The Dockerfile for the template manager is located at `./n8n_template_manager/Dockerfile`.

*   **Run the Docker Container:**
    ```bash
    docker run -p 8001:8000 \
      -e APP_HOST="0.0.0.0" \
      -e APP_PORT="8000" \
      -e LOG_LEVEL="INFO" \
      -e DATABASE_URL_POSTGRES="postgresql://user:pass@host:port/db" \
      # Or for SQLite:
      # -e DATABASE_URL_SQLITE="sqlite:///app/data/n8n_templates.db" \
      # -v /path/on/host/for_template_manager_db:/app/data \
      -v /path/on/host/for_template_manager_index:/app/whoosh_index \
      -v /path/on/host/template_manager_env_file:/app/.env \ # Mount your .env file
      n8n-template-manager-app
    ```
    *   Map the container's application port (default 8000, set by `APP_PORT` inside the container) to a host port (e.g., 8001).
    *   Pass environment variables directly using `-e` or mount a dedicated `.env` file into `/app/.env` in the container.
    *   **Data Persistence:**
        *   **Whoosh Index:** Mount a volume to `/app/whoosh_index` to persist the search index.
        *   **SQLite Database:** If using SQLite (i.e., `DATABASE_URL_POSTGRES` is *not* set), mount a volume for the directory containing the SQLite file (e.g., if `DATABASE_URL_SQLITE=sqlite:///app/data/n8n_templates.db`, mount `/app/data`).
        *   **PostgreSQL:** If using PostgreSQL, data persistence is handled by the PostgreSQL server itself (ideally also run in Docker with a persistent volume, or as a managed service).

## Accessing the Application

*   **Web UI:** `http://<APP_HOST>:<APP_PORT>/`
*   **API Documentation (Swagger UI):** `http://<APP_HOST>:<APP_PORT>/docs`
*   **API Documentation (ReDoc):** `http://<APP_HOST>:<APP_PORT>/redoc`
*   **API Base URL:** `http://<APP_HOST>:<APP_PORT>/api/v1`

## API Endpoints

Key API endpoints:

*   **`GET /api/v1/templates`**: Lists/searches templates. Params: `search`, `category`, `page`, `size`.
*   **`GET /api/v1/templates/{template_id}`**: Retrieves details for a specific template.
*   **`POST /api/v1/templates/import_to_n8n`**: Imports a template to an n8n instance.
    *   Body: `{ "template_id": int, "n8n_instance_url": str, "n8n_api_key": str }`
*   **`POST /api/v1/templates/sync_github`**: Triggers background sync from your GitHub repo.

(Refer to Swagger UI at `/docs` for full API details.)

## Backup Utility (SQLite)

If using SQLite, a script is provided to back up the database:
```bash
# Run from n8n_template_manager/ directory
python scripts/backup_db.py
```
Backups are stored in `n8n_template_manager/db_backups/`. This is not needed if using PostgreSQL.

## RAG Integration

The API provides workflow data (`raw_json`) that can be used by RAG systems:
1.  Search relevant workflows: `GET /api/v1/templates?search=query`
2.  Get full JSON: `GET /api/v1/templates/{template_id}`
3.  Feed `raw_json` to your RAG's language model.

## Root Docker Compose Setup

A `docker-compose.yml` file is provided at the root of the repository. This allows you to run the `n8n_template_manager`, the main `n8n` application, and a `PostgreSQL` database as interconnected services. Configuration for this setup is managed by a `.env` file at the repository root. See that `docker-compose.yml` and the root `.env.example` for more details on multi-service deployment.

## Future Enhancements / To-Do
*   **Advanced Duplicate Detection:** For n8n.io community templates.
*   **User Authentication:** For UI and API.
*   **UI Enhancements:** Detailed template view, visual workflow representation.
*   **Robust Background Task Processing:** Using Celery or similar for fetching/indexing.

---
*This README provides a comprehensive guide to setting up, running, and using the n8n Workflow Template Manager.*
