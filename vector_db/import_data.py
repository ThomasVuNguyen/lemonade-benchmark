# Extract text into paragraphs

import re

def extract_paragraphs(file_path):
    with open(file_path, 'r') as file:
        text = file.read()
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]

file_path = 'data/the-creative-act.txt'
paragraph_list = extract_paragraphs(file_path)
# print(paragraph_list)

# Turn paragraphs into vector

import chromadb
import uuid
client = chromadb.HttpClient()

data_name = 'the-creative-act'

collection = client.get_or_create_collection(data_name)


# Generate unique IDs for each document
ids = [f"doc_{uuid.uuid4().hex}" for _ in range(len(paragraph_list))]

# Now add the documents to the collection
collection.add(
    documents=paragraph_list,
    ids=ids,
)
results = collection.query(
    query_texts=["What is the book 'Creative Act' about?"],
    n_results=2,
    # where={"metadata_field": "is_equal_to_this"}, # optional filter
    # where_document={"$contains":"search_string"}  # optional filter
)

def extract_documents(result_dict):
    # Check if 'documents' key exists in the dictionary
    if 'documents' not in result_dict:
        return []

    # Extract the 'documents' list
    documents = result_dict['documents']

    # Flatten the nested list structure and remove duplicates
    flattened_docs = list(set([doc for sublist in documents for doc in sublist]))

    return flattened_docs
print(extract_documents(results))