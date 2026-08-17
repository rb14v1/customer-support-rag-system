import logging
import os

from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.storage.blob import BlobServiceClient

load_dotenv()

logger = logging.getLogger(__name__)

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_CHAT_DEPLOYMENT = os.getenv(
    "AZURE_OPENAI_CHAT_DEPLOYMENT"
)
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv(
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
)

AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY")
AZURE_SEARCH_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME")

AZURE_STORAGE_CONNECTION_STRING = os.getenv(
    "AZURE_STORAGE_CONNECTION_STRING"
)
AZURE_STORAGE_CONTAINER_NAME = os.getenv(
    "AZURE_STORAGE_CONTAINER_NAME"
)


def get_openai_client():
    """Create and return an Azure OpenAI client."""
    logger.info("Starting get_openai_client")
    try:
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION")

        if not endpoint or not api_key:
            logger.error("Missing required Azure OpenAI credentials (AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_API_KEY)")
            raise ValueError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY must be set in environment variables.")

        logger.info("Creating Azure OpenAI client for endpoint '%s'", endpoint)

        client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint,
        )

        logger.info("Finished get_openai_client successfully")
        return client

    except Exception:
        logger.exception("Failed to create Azure OpenAI client")
        raise


def get_search_client():
    """Create and return an Azure AI Search client."""
    logger.info("Starting get_search_client")
    try:
        endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        api_key = os.getenv("AZURE_SEARCH_API_KEY")
        index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")

        if not endpoint or not api_key or not index_name:
            logger.error("Missing required Azure AI Search configuration (AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_API_KEY, or AZURE_SEARCH_INDEX_NAME)")
            raise ValueError("AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_API_KEY, and AZURE_SEARCH_INDEX_NAME must be set.")

        logger.info(
            "Creating Azure AI Search client for index '%s'",
            index_name,
        )

        client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(api_key),
        )

        logger.info("Finished get_search_client successfully")
        return client

    except Exception:
        logger.exception("Failed to create Azure AI Search client")
        raise


def get_blob_service_client():
    """Create and return an Azure Blob Storage client."""
    logger.info("Starting get_blob_service_client")
    try:
        conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        if not conn_str:
            logger.error("Missing required AZURE_STORAGE_CONNECTION_STRING environment variable")
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING must be set in environment variables.")

        logger.info("Creating Azure Blob Storage client from connection string")

        client = BlobServiceClient.from_connection_string(conn_str)

        logger.info("Finished get_blob_service_client successfully")
        return client

    except Exception:
        logger.exception(
            "Failed to create Azure Blob Storage client"
        )
        raise


def get_blob_container_client():
    """Return the Azure Blob Storage container client."""
    logger.info("Starting get_blob_container_client")
    try:
        container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
        if not container_name:
            logger.error("Missing required AZURE_STORAGE_CONTAINER_NAME environment variable")
            raise ValueError("AZURE_STORAGE_CONTAINER_NAME must be set in environment variables.")

        logger.info(
            "Getting Blob Storage container '%s'",
            container_name,
        )

        blob_service_client = get_blob_service_client()

        client = blob_service_client.get_container_client(container_name)

        logger.info("Finished get_blob_container_client successfully")
        return client

    except Exception:
        logger.exception(
            "Failed to create Blob container client"
        )
        raise