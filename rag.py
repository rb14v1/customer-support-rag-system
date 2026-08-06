from retrieve import retrieve_documents
from azure_config import get_openai_client


SYSTEM_PROMPT = """
You are a customer support assistant.

Answer ONLY using the provided context.

If the answer isn't present in the context, politely say you don't know.

Keep answers concise and helpful.
"""


def build_context(documents):

    context = ""

    for doc in documents:
        context += doc["content"] + "\n\n"

    return context


def ask_rag(question):

    docs = retrieve_documents(question)

    context = build_context(docs)

    prompt = f"""
Context:

{context}

Question:

{question}

Answer:
"""

    client = get_openai_client()

    response = client.chat.completions.create(

        model="gpt-4o-mini",

        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": prompt
            }
        ],

        temperature=0.2
    )

    return response.choices[0].message.content