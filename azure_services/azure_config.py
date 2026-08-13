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
    try:
        logger.info("Creating Azure OpenAI client")

        client = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
        )

        logger.info("Azure OpenAI client created successfully")
        return client

    except Exception:
        logger.exception("Failed to create Azure OpenAI client")
        raise


def get_search_client():
    """Create and return an Azure AI Search client."""
    try:
        logger.info(
            "Creating Azure AI Search client for index '%s'",
            AZURE_SEARCH_INDEX_NAME,
        )

        client = SearchClient(
            endpoint=AZURE_SEARCH_ENDPOINT,
            index_name=AZURE_SEARCH_INDEX_NAME,
            credential=AzureKeyCredential(
                AZURE_SEARCH_API_KEY
            ),
        )

        logger.info("Azure AI Search client created successfully")
        return client

    except Exception:
        logger.exception("Failed to create Azure AI Search client")
        raise


def get_blob_service_client():
    """Create and return an Azure Blob Storage client."""
    try:
        logger.info("Creating Azure Blob Storage client")

        client = BlobServiceClient.from_connection_string(
            AZURE_STORAGE_CONNECTION_STRING
        )

        logger.info("Azure Blob Storage client created successfully")
        return client

    except Exception:
        logger.exception(
            "Failed to create Azure Blob Storage client"
        )
        raise


def get_blob_container_client():
    """Return the Azure Blob Storage container client."""
    try:
        logger.info(
            "Getting Blob Storage container '%s'",
            AZURE_STORAGE_CONTAINER_NAME,
        )

        blob_service_client = get_blob_service_client()

        client = blob_service_client.get_container_client(
            AZURE_STORAGE_CONTAINER_NAME
        )

        logger.info("Blob container client created successfully")
        return client

    except Exception:
        logger.exception(
            "Failed to create Blob container client"
        )
        raise