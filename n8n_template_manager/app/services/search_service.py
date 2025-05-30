import os
import pathlib
import json
import logging
from whoosh.index import create_in, open_dir, exists_in
from whoosh.fields import Schema, TEXT, ID, KEYWORD, STORED
from whoosh.qparser import QueryParser
from whoosh.writing import LockError
from sqlalchemy.orm import Session # For type hinting if db session is passed

# Configure basic logging for search service
logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO) # Set level in main application logging config
# Prevent duplicate logs if root logger is already configured
if not logger.hasHandlers():
    # Basic setup if run standalone or not configured by main app
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(),
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# Define the base directory for the index relative to this file's location
# Correctly points to `n8n_template_manager/whoosh_index/`
APP_ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
INDEX_DIR = APP_ROOT_DIR / "whoosh_index"

# Define the Whoosh schema
# The 'id' field stores the Database Primary Key of the Workflow record.
# It must be unique in the Whoosh index.
class WorkflowSchema(Schema):
    id = ID(stored=True, unique=True)  # Stores Workflow.id (Database PK) as string
    name = TEXT(stored=True, field_boost=2.0)
    description = TEXT(stored=True)
    category = KEYWORD(stored=True, scorable=True, lowercase=True) # lowercase for case-insensitive matching
    nodes_summary = TEXT(stored=True)  # Space-separated string of node types
    tags = KEYWORD(stored=True, scorable=True, commas=True, lowercase=True) # Comma-separated, lowercase
    source_path = STORED() # Path to the original JSON file, e.g., github URL or local path

def get_index():
    """
    Opens an existing Whoosh index or creates a new one if it doesn't exist.
    """
    if not INDEX_DIR.exists():
        logger.info(f"Index directory {INDEX_DIR} not found. Creating new index.")
        os.makedirs(INDEX_DIR, exist_ok=True)
        # Ensure schema is applied at creation
        ix = create_in(INDEX_DIR, WorkflowSchema, indexname="MAIN")
        logger.info(f"New index 'MAIN' created in {INDEX_DIR}")
    else:
        try:
            # Try to open the 'MAIN' index directly
            ix = open_dir(INDEX_DIR, indexname="MAIN", schema=WorkflowSchema)
            logger.info(f"Opened existing index 'MAIN' from {INDEX_DIR}")
        except Exception as e: # More specific exception like IndexMissingError could be caught
            logger.warning(f"Could not open existing index 'MAIN' from {INDEX_DIR} (Error: {e}). Attempting to create.", exc_info=True)
            # This could happen if the directory exists but is empty or index is corrupt
            os.makedirs(INDEX_DIR, exist_ok=True) # Ensure dir exists
            ix = create_in(INDEX_DIR, WorkflowSchema, indexname="MAIN")
            logger.info(f"New index 'MAIN' created after failing to open existing one.")
    return ix

def _prepare_document_for_whoosh(workflow_model_instance):
    """
    Prepares a dictionary document for Whoosh from a Workflow SQLAlchemy model instance.
    The 'id' in the returned dict is the database primary key of the workflow.
    """
    # Ensure 'id' (database PK) is a string for Whoosh ID field
    # This ID is critical for updates and deletions.
    workflow_db_pk_str = str(workflow_model_instance.id)

    # Convert nodes_summary (JSON list string) to space-separated string
    try:
        nodes_list = json.loads(workflow_model_instance.nodes_summary or "[]")
    except json.JSONDecodeError:
        logger.warning(f"Invalid JSON in nodes_summary for DB ID {workflow_db_pk_str}: {workflow_model_instance.nodes_summary}", exc_info=True)
        nodes_list = []
    nodes_text = " ".join(sorted(list(set(str(node).strip() for node in nodes_list if str(node).strip()))))

    # Convert tags (JSON list string) to comma-separated string
    try:
        tags_list = json.loads(workflow_model_instance.tags or "[]")
    except json.JSONDecodeError:
        logger.warning(f"Invalid JSON in tags for DB ID {workflow_db_pk_str}: {workflow_model_instance.tags}", exc_info=True)
        tags_list = []
    # Ensure tags are strings and clean them up
    tags_text = ",".join(sorted(list(set(str(tag).strip().lower() for tag in tags_list if str(tag).strip()))))

    description_text = workflow_model_instance.description if workflow_model_instance.description is not None else ""

    doc = {
        "id": workflow_db_pk_str, # Database Primary Key
        "name": workflow_model_instance.name,
        "description": description_text,
        "category": (workflow_model_instance.category or "").lower(), # Ensure category is not None and lowercase
        "nodes_summary": nodes_text,
        "tags": tags_text,
        "source_path": workflow_model_instance.source_path
    }
    logger.debug(f"Whoosh document fields prepared for DB ID {workflow_db_pk_str}: Name: {doc['name']}, Category: {doc['category']}, Tags: {doc['tags']}")
    return doc

def index_workflow(workflow_model_instance):
    """
    Gets the Whoosh index and indexes/updates a single workflow model instance.
    Uses `update_document` to add if new or overwrite if ID (DB PK) exists.
    """
    logger.info(f"Starting indexing for workflow with DB Primary Key: {workflow_model_instance.id}")
    try:
        ix = get_index()
        doc_to_index = _prepare_document_for_whoosh(workflow_model_instance)
        
        with ix.writer() as writer:
            # update_document will add the document if it's new (based on unique 'id' field),
            # or update it if a document with that 'id' already exists.
            writer.update_document(**doc_to_index)
        logger.info(f"Successfully indexed/updated workflow with DB PK: {workflow_model_instance.id}, Name: '{workflow_model_instance.name}'")
    except LockError as le:
        logger.error(f"Whoosh LockError while indexing DB PK {workflow_model_instance.id}: {le}. This might be due to concurrent access. Retrying may be necessary.", exc_info=True)
        # Depending on application needs, you might implement a retry mechanism here.
    except Exception as e:
        logger.error(f"Failed to index/update workflow DB PK {workflow_model_instance.id}: {e}", exc_info=True)


def delete_workflow_from_index(workflow_db_pk: int, db: Optional[Session] = None): # db param for API consistency, not used here
    """
    Deletes a workflow document from the Whoosh index using its database primary key.
    `workflow_db_pk` is the integer primary key from the database.
    """
    workflow_db_pk_str = str(workflow_db_pk) # Whoosh stores it as string
    logger.info(f"Attempting to delete workflow with DB PK: {workflow_db_pk_str} from Whoosh index.")
    try:
        ix = get_index()
        with ix.writer() as writer:
            # The 'id' field in Whoosh schema corresponds to the database primary key.
            writer.delete_by_term('id', workflow_db_pk_str)
        logger.info(f"Successfully deleted workflow with DB PK: {workflow_db_pk_str} from Whoosh index (if it existed).")
    except LockError as le:
        logger.error(f"Whoosh LockError while deleting DB PK {workflow_db_pk_str}: {le}. Concurrent access issue?", exc_info=True)
    except Exception as e:
        logger.error(f"Failed to delete workflow DB PK {workflow_db_pk_str} from index: {e}", exc_info=True)


# Example Usage (for testing this module directly)
if __name__ == '__main__':
    logger.info("Running search_service.py directly for testing.")
    
    # Mock Workflow SQLAlchemy model instance for testing
    class MockWorkflow:
        def __init__(self, id, name, description, category, nodes_summary_json, tags_json, source_path):
            self.id = id # This is the Database Primary Key (integer for this mock)
            self.name = name
            self.description = description
            self.category = category
            self.nodes_summary = nodes_summary_json # JSON string
            self.tags = tags_json # JSON string
            self.source_path = source_path

    # For a clean test, you might want to remove the index directory first.
    # import shutil
    # if INDEX_DIR.exists():
    #     logger.info(f"Test: Removing existing index directory {INDEX_DIR} for a fresh test.")
    #     shutil.rmtree(INDEX_DIR)

    logger.info("Creating mock workflow instances...")
    mock_wf1 = MockWorkflow(
        id=1, # DB PK
        name="My First Test Workflow",
        description="Description for the first test workflow. Contains http node.",
        category="Testing Category A",
        nodes_summary_json='["n8n-nodes-base.httpRequest", "n8n-nodes-base.if"]',
        tags_json='["test", "example", "http", "alpha"]',
        source_path="/path/to/workflow1.json"
    )
    mock_wf2 = MockWorkflow(
        id=2, # DB PK
        name="My Second Awesome Workflow",
        description="Description for second workflow. Has schedule and email.",
        category="Testing Category B",
        nodes_summary_json='["n8n-nodes-base.scheduleTrigger", "n8n-nodes-base.emailSend"]',
        tags_json='["test", "schedule", "email", "beta"]',
        source_path="/path/to/workflow2.json"
    )

    logger.info("Attempting to index mock workflows...")
    try:
        index_workflow(mock_wf1)
        index_workflow(mock_wf2)
        logger.info("Mock workflow indexing test completed.")
    except Exception as e:
        logger.error(f"Error during mock workflow indexing test: {e}", exc_info=True)

    # Test updating an existing document
    logger.info("Attempting to update mock_wf1...")
    mock_wf1_updated = MockWorkflow(
        id=1, # Same DB PK
        name="My First Test Workflow (Updated Name)",
        description="UPDATED Description for first workflow. Still has http node.",
        category="Testing Category A", # Category unchanged
        nodes_summary_json='["n8n-nodes-base.httpRequest", "n8n-nodes-base.if", "n8n-nodes-base.function"]', # Added a node
        tags_json='["test", "example", "http", "alpha", "updated"]', # Added a tag
        source_path="/path/to/workflow1_v2.json" # Source path might change if versioned
    )
    try:
        index_workflow(mock_wf1_updated)
        logger.info("Mock workflow update test completed.")
    except Exception as e:
        logger.error(f"Error during mock workflow update test: {e}", exc_info=True)


    # Test searching
    try:
        ix_search = get_index() # Renamed to avoid conflict with outer scope 'ix' if any
        with ix_search.searcher() as searcher:
            # Search for the updated name
            query_parser = QueryParser("name", schema=ix_search.schema)
            query_name = query_parser.parse("Updated Name")
            results_name = searcher.search(query_name)
            logger.info(f"Found {len(results_name)} results for 'Updated Name':")
            for hit in results_name:
                logger.info(f"  DB_ID (from Whoosh 'id'): {hit['id']}, Name: {hit['name']}, Desc: {hit['description'][:30]}..., Tags: {hit['tags']}")

            # Search for a tag
            query_parser_tags = QueryParser("tags", schema=ix_search.schema) # Use MultifieldParser for more fields
            query_tags = query_parser_tags.parse("beta")
            results_tags = searcher.search(query_tags)
            logger.info(f"Found {len(results_tags)} results for tag 'beta':")
            for hit in results_tags:
                 logger.info(f"  DB_ID (from Whoosh 'id'): {hit['id']}, Name: {hit['name']}, Category: {hit['category']}, Tags: {hit['tags']}")

            # Search for a node type (nodes_summary is TEXT, so needs careful parsing if searching specific nodes)
            # For simple text search in nodes_summary:
            query_parser_nodes = QueryParser("nodes_summary", schema=ix_search.schema)
            query_nodes = query_parser_nodes.parse("n8n-nodes-base.function") # Search for the added node
            results_nodes = searcher.search(query_nodes)
            logger.info(f"Found {len(results_nodes)} results for node 'n8n-nodes-base.function':")
            for hit in results_nodes:
                 logger.info(f"  DB_ID (from Whoosh 'id'): {hit['id']}, Name: {hit['name']}, Nodes: {hit['nodes_summary']}")

    except Exception as e:
        logger.error(f"Error during search test: {e}", exc_info=True)

    # Test deleting a document
    logger.info(f"Attempting to delete workflow with DB PK: {mock_wf2.id} from index...")
    try:
        delete_workflow_from_index(mock_wf2.id) # Pass the DB PK (integer)
        logger.info("Mock workflow deletion test completed.")
    except Exception as e:
        logger.error(f"Error during mock workflow deletion test: {e}", exc_info=True)

    # Verify deletion
    try:
        ix_verify = get_index()
        with ix_verify.searcher() as searcher:
            # Try to find the deleted document by its DB PK (stored as 'id' in Whoosh)
            # QueryParser default field is often the first field, or specify schema's default
            # For precise ID search:
            results_deleted = searcher.search(QueryParser("id", schema=ix_verify.schema).parse(str(mock_wf2.id)))
            if results_deleted:
                logger.error(f"Verification FAILED: Workflow with DB PK {mock_wf2.id} was found in index after deletion attempt.")
            else:
                logger.info(f"Verification SUCCESS: Workflow with DB PK {mock_wf2.id} was NOT found in index after deletion.")
    except Exception as e:
        logger.error(f"Error during deletion verification: {e}", exc_info=True)

    logger.info("Search service direct execution test finished.")
