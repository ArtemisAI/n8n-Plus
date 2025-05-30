# Project Roadmap

This document outlines the plan and progress for addressing the n8n template management enhancements.

## Phase 1: Core Enhancements and Setup

*   [x] **1. Setup `roadmap.md`**: Create the `roadmap.md` file and populate it with the initial plan.
    *   Status: Done
    *   Details: This task.

*   [x] **2. Environment Configuration (.env) for `n8n_template_manager`**:
    *   Status: Completed
    *   Details: Implement `.env` file support for managing database connection strings (PostgreSQL), API keys, and other configurations. Update relevant Python files (`main.py`, `database.py`) to use these variables.

*   [x] **3. PostgreSQL Integration for `n8n_template_manager`**:
    *   Status: Completed
    *   Details: Modify `n8n_template_manager/app/db/database.py` to support PostgreSQL. Ensure `create_db_and_tables()` works. Update Dockerfile if necessary. Provide sample `.env` config.

*   [x] **4. GitHub Personal Template Syncing**:
    *   Status: Completed
    *   Details: Create a new service (`github_template_fetcher.py`) to clone/pull a user-defined GitHub repository, scan for n8n workflow JSON files, process them (checking duplicates against PostgreSQL), and add/update them in the database and search index. Add an API endpoint to trigger this sync. Update README.

*   [x] **5. n8n Docker Compose Setup at Root**:
    *   Status: Completed
    *   Details: Create or modify a `docker-compose.yml` at the repository root to run the main n8n application. Optionally, integrate `n8n_template_manager` as a service, connected to PostgreSQL.

*   [x] **6. Refine Template Organization and Duplicate Handling**:
    *   Status: Completed
    *   Details: Review if current organization/sorting and `id`-based duplicate detection are sufficient, especially for GitHub-sourced templates. Address updating templates if content changes but `id` remains the same.

*   [x] **7. Documentation and Final Review**:
    *   Status: Completed
    *   Details: Update `n8n_template_manager/README.md` with all new features. Ensure `roadmap.md` is fully updated. Final review of all changes.

*   [ ] **8. Submit Changes**:
    *   Status: Pending
    *   Details: Commit all the completed work with appropriate messages.

## Progress Updates

Completed Step 2: Implemented .env configuration for the template manager, added `python-dotenv`, and updated database/main scripts to use environment variables.

Completed Step 3: Ensured `psycopg2-binary` is in requirements, updated Dockerfile with PostgreSQL client libraries. `database.py` is prepared for PostgreSQL connection via .env.

Completed Step 4: Implemented GitHub Personal Template Syncing feature. Added `GitPython` to requirements, created `github_template_fetcher.py` service, added an API endpoint for sync, and updated README.

Completed Step 5: Created a root `docker-compose.yml` to run n8n, PostgreSQL, and the `n8n_template_manager` as services. Added a root `.env` file for managing configurations for the compose setup.

Completed Step 6: Refined template organization and duplicate handling. Updated `github_template_fetcher.py` for intelligent primary key assignment (using JSON ID if valid and available, else auto-generating) and to preserve existing primary keys on updates. Ensured consistent metadata extraction. Updated `search_service.py` to use `update_document` for indexing (add/update) and implemented `delete_workflow_from_index` for handling updates correctly in the search index.

Completed Step 7: Updated `n8n_template_manager/README.md` with details on PostgreSQL, .env configuration, GitHub sync, and Docker usage. Reviewed all documentation for accuracy. `roadmap.md` is now fully updated.

*(This section will be updated as tasks are completed.)*
