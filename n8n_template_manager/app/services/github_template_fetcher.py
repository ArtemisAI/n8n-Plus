import os
import json
import logging
import tempfile
import shutil
from pathlib import Path
from git import Repo, GitCommandError
from sqlalchemy.orm import Session
from sqlalchemy import func
from dotenv import load_dotenv

from app.db.database import SessionLocal, create_db_and_tables
from app.models.workflow import Workflow
from app.services.search_service import index_workflow, delete_workflow_from_index # Added delete_workflow_from_index

SERVICE_FILE_DIR = Path(__file__).resolve().parent
BASE_DIR = SERVICE_FILE_DIR.parent.parent
dotenv_path = BASE_DIR / '.env'

if dotenv_path.exists():
    load_dotenv(dotenv_path)
else:
    # Fallback for environments where .env might be in the same dir as the script (e.g. direct execution)
    # or if APP_ROOT_DIR is set pointing to the project root for Docker.
    app_root_dir_env = os.getenv("APP_ROOT_DIR")
    if app_root_dir_env:
        load_dotenv(Path(app_root_dir_env) / '.env')
    else:
        load_dotenv() # Load from current dir or rely on system env vars

logger = logging.getLogger(__name__)
if not logger.hasHandlers(): # Check if logger already has handlers
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=log_level_str, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


GITHUB_REPO_URL = os.getenv("GITHUB_REPO_URL_PERSONAL_TEMPLATES")
GIT_CLONE_DIR_PARENT = tempfile.gettempdir()
GIT_CLONE_DIR_NAME = "n8n_personal_templates_repo"


def get_workflow_json_file_id(workflow_data: dict, filepath: Path) -> str:
    """Gets an ID string from workflow JSON data's 'id' field or filename."""
    # n8n workflows might have an 'id' in their JSON structure, but it's not guaranteed to be globally unique
    # or suitable as a database primary key directly if it's not an integer or too long.
    # For GitHub sourced items, we'll primarily rely on source_path for uniqueness.
    # This function is to get *a* candidate ID from the file, which might be used
    # if it's an integer and available, otherwise PK will be auto-generated.
    explicit_id = workflow_data.get('id')
    if explicit_id:
        return str(explicit_id)
    return filepath.stem # Filename without extension

def process_github_workflow_file(filepath: Path, repo_relative_path: str, db: Session, repo_url_for_source: str):
    try:
        raw_json_content = filepath.read_text(encoding='utf-8')
        workflow_data = json.loads(raw_json_content)

        json_file_id_str = get_workflow_json_file_id(workflow_data, filepath)

        source_path = f"github://{repo_url_for_source}/{repo_relative_path}"
        existing_workflow_by_source = db.query(Workflow).filter(Workflow.source_path == source_path).first()

        db_workflow_id_to_use = None # This will be the actual PK for the DB record

        if existing_workflow_by_source:
            if existing_workflow_by_source.raw_json == raw_json_content:
                logger.info(f"Unchanged: {source_path} (ID: {existing_workflow_by_source.id}). Skipping.")
                return False
            else:
                logger.info(f"Updating: {source_path} (Existing DB ID: {existing_workflow_by_source.id})")
                # Preserve existing database primary key for the update
                db_workflow_id_to_use = existing_workflow_by_source.id
                # Remove old version from search index before updating DB
                try:
                    delete_workflow_from_index(existing_workflow_by_source.id, db) # Pass db_pk
                    logger.info(f"Removed old version of {source_path} (DB ID: {db_workflow_id_to_use}) from search index.")
                except Exception as idx_del_exc:
                    logger.error(f"Error deleting old version of {source_path} (DB ID: {db_workflow_id_to_use}) from index: {idx_del_exc}", exc_info=True)

                # Delete the old DB record before adding the new one with the same PK (if ORM requires it)
                # Or, update fields directly on `existing_workflow_by_source`
                # For simplicity here, we'll delete then re-add if updating an existing PK is complex with current model setup
                # However, it's usually better to update in place:
                # existing_workflow_by_source.name = new_name
                # ... etc ...
                # db.commit()
                # For now, let's assume we delete and re-create the record if content changed, using the same PK.
                # This means the new Workflow object below will need its `id` field explicitly set.
                db.delete(existing_workflow_by_source)
                db.flush() # Ensure delete is processed before attempting to insert new with same PK (if that's the strategy)

        else: # New template (source_path not found)
            logger.info(f"New template from GitHub: {source_path}")
            # Try to use json_file_id_str as database PK if it's an integer and not already taken
            try:
                candidate_pk = int(json_file_id_str)
                # Check if this integer PK is already in use by *any* workflow
                existing_by_candidate_pk = db.query(Workflow).filter(Workflow.id == candidate_pk).first()
                if not existing_by_candidate_pk:
                    db_workflow_id_to_use = candidate_pk
                    logger.info(f"Attempting to use json_file_id {candidate_pk} as new DB PK for {source_path}.")
                else:
                    logger.info(f"json_file_id {candidate_pk} is already in use as a DB PK. Will auto-generate PK for {source_path}.")
                    db_workflow_id_to_use = None # Let DB auto-generate
            except ValueError:
                logger.info(f"json_file_id '{json_file_id_str}' is not an integer. Will auto-generate PK for {source_path}.")
                db_workflow_id_to_use = None # Let DB auto-generate


        name = workflow_data.get('name', filepath.stem)
        # Ensure description is a string, even if null in JSON
        description = workflow_data.get('description', "") or ""

        category_parts = [part.strip() for part in repo_relative_path.split('/')[:-1] if part.strip()]
        category = "/".join(category_parts) if category_parts else "GitHub Imported"
        category = category.replace("_", " ").replace("-", " ").title()

        nodes_summary_list = []
        # Accommodate both direct 'nodes' list and nested 'workflow.nodes'
        workflow_nodes_data = workflow_data.get('workflow', {}).get('nodes', [])
        if not workflow_nodes_data and 'nodes' in workflow_data: # Check root level if not in 'workflow'
            workflow_nodes_data = workflow_data.get('nodes', [])

        for node in workflow_nodes_data:
            node_type = node.get('type')
            if node_type and node_type not in nodes_summary_list:
                nodes_summary_list.append(node_type)

        nodes_summary_json = json.dumps(sorted(list(set(nodes_summary_list))))

        tags_list = [tag.strip().lower() for tag in category.split('/') if tag.strip() and tag.lower() != "github imported"]
        tags_list.append("github")
        # Add parts of the filename to tags if they are not too generic
        filename_tags = [part.strip().lower() for part in filepath.stem.replace("_", "-").split("-") if part.strip() and len(part) > 2]
        tags_list.extend(filename_tags)
        tags_json = json.dumps(sorted(list(set(tags_list))))

        # Create the new Workflow object
        workflow_params = {
            "name": name,
            "description": description,
            "source_path": source_path,
            "category": category,
            "raw_json": raw_json_content,
            "nodes_summary": nodes_summary_json,
            "tags": tags_json
        }
        if db_workflow_id_to_use is not None: # If we determined a specific PK to use (either preserved or new candidate)
            workflow_params["id"] = db_workflow_id_to_use

        workflow_entry = Workflow(**workflow_params)

        db.add(workflow_entry)
        db.commit() # Commit to save the new/updated workflow and get its actual PK (if auto-generated)

        # workflow_entry.id will now be populated, even if it was auto-generated.
        logger.info(f"Successfully Added/Updated in DB: '{name}' (DB ID: {workflow_entry.id}) from {source_path}")

        # Index the newly added/updated workflow
        index_workflow(workflow_entry) # Assumes index_workflow uses workflow_entry.id as the document ID for Whoosh
        logger.info(f"Indexed: '{name}' (DB ID: {workflow_entry.id}) from GitHub.")
        return True

    except Exception as e:
        logger.error(f"Error processing GitHub workflow file {repo_relative_path}: {e}", exc_info=True)
        db.rollback() # Rollback in case of error during processing of one file
    return False

def fetch_templates_from_github():
    if not GITHUB_REPO_URL:
        logger.warning("GITHUB_REPO_URL_PERSONAL_TEMPLATES not set in .env. Skipping GitHub template fetching.")
        return {"status": "skipped", "message": "GitHub repository URL not configured."}

    repo_clone_path = Path(GIT_CLONE_DIR_PARENT) / GIT_CLONE_DIR_NAME

    try:
        logger.info(f"Attempting to clone/pull GitHub repo '{GITHUB_REPO_URL}' into '{repo_clone_path}'")
        if repo_clone_path.exists() and repo_clone_path.is_dir():
            logger.info("Repository exists, pulling latest changes.")
            repo = Repo(repo_clone_path)
            origin = repo.remotes.origin
            origin.pull()
            logger.info("Pull successful.")
        else:
            logger.info("Repository does not exist locally, cloning.")
            if repo_clone_path.exists(): # If it exists but not a dir, or some other issue
                shutil.rmtree(repo_clone_path, ignore_errors=True)
                logger.info(f"Removed existing file/link at {repo_clone_path} before cloning.")
            Repo.clone_from(GITHUB_REPO_URL, repo_clone_path)
            logger.info("Clone successful.")
    except GitCommandError as git_err:
        logger.error(f"Git command error during repository operation: {git_err}", exc_info=True)
        # Optionally, remove the potentially corrupted clone directory
        # shutil.rmtree(repo_clone_path, ignore_errors=True)
        return {"status": "error", "message": f"Git command failed: {str(git_err)}"}
    except Exception as e: # Catch other exceptions like permission errors, etc.
        logger.error(f"An unexpected error occurred during Git operation: {e}", exc_info=True)
        # shutil.rmtree(repo_clone_path, ignore_errors=True)
        return {"status": "error", "message": f"Git operation failed due to an unexpected error: {str(e)}"}


    json_files = list(repo_clone_path.rglob('*.json'))
    if not json_files:
        logger.info(f"No JSON files found in the cloned repository at {repo_clone_path}.")
        return {"status": "success", "message": "No JSON files found in the GitHub repository.", "added_or_updated": 0, "skipped_or_errors": 0}

    logger.info(f"Found {len(json_files)} JSON files in the repository. Starting processing...")

    # Ensure DB tables are created if they weren't already
    try:
        create_db_and_tables()
    except Exception as db_init_err:
        logger.error(f"Failed to initialize database and tables: {db_init_err}", exc_info=True)
        return {"status": "error", "message": "Database initialization failed."}

    db: Session = SessionLocal()
    success_count = 0
    error_or_skipped_count = 0

    # Extract a cleaner repo URL for the source_path, removing potential user:pass@
    clean_repo_url_parts = GITHUB_REPO_URL.split('://')
    if len(clean_repo_url_parts) > 1:
        clean_repo_url = clean_repo_url_parts[0] + "://" + clean_repo_url_parts[1].split('@')[-1]
    else: # Should not happen for valid URLs
        clean_repo_url = GITHUB_REPO_URL


    for filepath in json_files:
        repo_relative_path = str(filepath.relative_to(repo_clone_path))
        logger.debug(f"Processing file: {repo_relative_path}")
        if process_github_workflow_file(filepath, repo_relative_path, db, clean_repo_url):
            success_count += 1
        else:
            error_or_skipped_count += 1

    db.close()
    logger.info(f"GitHub sync finished. Added/Updated: {success_count}, Skipped/Errors: {error_or_skipped_count}")
    return {
        "status": "success",
        "message": "GitHub synchronization process completed.",
        "added_or_updated": success_count,
        "skipped_or_errors": error_or_skipped_count
    }

if __name__ == "__main__":
    # This allows direct execution for testing purposes
    logger.info("Starting GitHub template fetcher directly (for testing or cron job).")

    # Example: Create a dummy .env if it doesn't exist for direct run
    if not dotenv_path.exists() and not os.getenv("GITHUB_REPO_URL_PERSONAL_TEMPLATES"):
        logger.warning(f"No .env file found at {dotenv_path} and GITHUB_REPO_URL_PERSONAL_TEMPLATES not set. Please configure.")
        # Create a dummy .env for testing if you want, or ensure one exists.
        # For example:
        # with open(".env", "w") as f:
        #     f.write("GITHUB_REPO_URL_PERSONAL_TEMPLATES=https://github.com/user/repo.git\n")
        #     f.write("DATABASE_URL_SQLITE=sqlite:///./test_github_fetcher.db\n")
        # logger.info("Created a dummy .env for testing. Please edit it with actual values if needed.")
        # load_dotenv() # Reload .env after creating it

    result = fetch_templates_from_github()
    logger.info(f"Standalone script execution finished with result: {result}")
