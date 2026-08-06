from azure_config import get_embedding_client
from search_service import search_documents


def generate_query_embedding(query):

    client = get_embedding_client()

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=query
    )

    return response.data[0].embedding


def retrieve_documents(query, top_k=5):

    embedding = generate_query_embedding(query)

    docs = search_documents(
        embedding,
        top_k=top_k
    )

    return docs