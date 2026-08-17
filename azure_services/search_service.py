import logging
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from azure.search.documents.models import VectorizedQuery

logger = logging.getLogger(__name__)


def ensure_search_index(endpoint, key, index_name, embedding_dim=1536):
    """Ensure Azure AI Search index exists with proper vector and text schema."""
    logger.info("Starting ensure_search_index for index '%s'", index_name)
    try:
        index_client = SearchIndexClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(key),
        )

        existing_indexes = [i.name for i in index_client.list_indexes()]
        if index_name in existing_indexes:
            logger.info("Index '%s' already exists in Azure AI Search.", index_name)
            logger.info("Finished ensure_search_index (already exists)")
            return

        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SearchableField(name="document_name", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="page_number", type=SearchFieldDataType.Int32, filterable=True),
            SearchField(
                name="vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=embedding_dim,
                vector_search_profile_name="myHnswProfile",
            ),
        ]

        vector_search = VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="myHnswConfig")],
            profiles=[
                VectorSearchProfile(
                    name="myHnswProfile",
                    algorithm_configuration_name="myHnswConfig",
                )
            ],
        )

        index = SearchIndex(name=index_name, fields=fields, vector_search=vector_search)
        index_client.create_or_update_index(index)
        logger.info("Finished ensure_search_index successfully for index '%s'", index_name)
    except Exception:
        logger.exception("Failed to create or update Azure AI Search index '%s'", index_name)
        raise


def upload_documents(search_client, documents):
    """Upload documents to Azure AI Search."""
    logger.info("Starting upload_documents (%d documents)", len(documents) if documents else 0)
    try:
        result = search_client.upload_documents(
            documents=documents
        )

        logger.info(
            "Finished upload_documents successfully"
        )

        return result

    except Exception:
        logger.exception(
            "Failed to upload documents to Azure AI Search"
        )
        raise


def search_documents(search_client, query, query_vector=None, top=5):
    """Search Azure AI Search for relevant documents using hybrid or text search."""
    logger.info("Starting search_documents for query: '%s'", query)
    try:
        vector_queries = []
        if query_vector is not None:
            vector_queries.append(
                VectorizedQuery(
                    vector=query_vector,
                    k_nearest_neighbors=top,
                    fields="vector",
                )
            )

        results = search_client.search(
            search_text=query,
            vector_queries=vector_queries if vector_queries else None,
            top=top,
        )

        documents = list(results)

        logger.info(
            "Finished search_documents successfully (retrieved %d documents)",
            len(documents),
        )

        return documents

    except Exception:
        logger.exception(
            "Failed to search Azure AI Search"
        )
        raise


def delete_documents(search_client, document_ids):
    """Delete documents from Azure AI Search."""
    logger.info("Starting delete_documents (%d document IDs)", len(document_ids) if document_ids else 0)
    try:
        documents = [
            {
                "@search.action": "delete",
                "id": document_id,
            }
            for document_id in document_ids
        ]

        result = search_client.upload_documents(
            documents=documents
        )

        logger.info(
            "Finished delete_documents successfully"
        )

        return result

    except Exception:
        logger.exception(
            "Failed to delete documents"
        )
        raise