from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain_community.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddings,
)
from langchain_text_splitters import CharacterTextSplitter
import os
from chromadb.utils import embedding_functions
from langchain.docstore.document import Document
from src.common_util import convert_to_single_word
from src.logger import Logger
from botocore.exceptions import ClientError
from src.config import Config

logger = Logger()
config = Config()

class ChromaDb:
    def __init__(self):
        chroma_path = config.get_chroma_path()
        embedding_model = config.get_chroma_embedding()

        # create the open-source embedding function
        embedding_function = SentenceTransformerEmbeddings(model_name=embedding_model)
        self.text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
        # load from disk
        if not os.path.exists(chroma_path):
            os.makedirs(chroma_path, exist_ok=True)
            loader = TextLoader("./pre-knowledge/default.txt")
            documents = loader.load()
            docs = self.text_splitter.split_documents(documents)      
            self.db = Chroma.from_documents(
                docs,
                embedding=embedding_function,
                persist_directory=chroma_path
            )
        else:
            self.db = Chroma(persist_directory=chroma_path, embedding_function=embedding_function)
        logger.info("Chroma initialized")

    def get_text_content(self, file_path):
        loader = TextLoader(file_path)
        documents = loader.load()
        file_content = documents[0].page_content
        return file_content
    
    def add_doc(self, doc_file_path):
        # load the document and split it into chunks
        loader = TextLoader(doc_file_path)
        documents = loader.load()

        # split it into chunks
        docs = self.text_splitter.split_documents(documents)
        self.db.add_documents(docs)
        logger.info(f"\nAdded document to chroma {doc_file_path}")
    
    def add_csv(self, csv_file_path):
        # load the document and split it into chunks
        loader = CSVLoader(file_path=csv_file_path)

        documents = loader.load()

        # split it into chunks
        docs = self.text_splitter.split_documents(documents)
        self.db.add_documents(docs)
        logger.info(f"\nAdded document to chroma {csv_file_path}")

    def add_text(self, name, content):
        doc =  Document(
            page_content=content,
            metadata={
                "source": name,
                "page": 1,
                "category": "answer"
        })
        self.db.add_documents([doc])
        logger.info(f"\nAdded content to chroma {name}")

    def query(self, query):
        docs = self.db.similarity_search(query)
        result = ""
        if len(docs) > 0:
            result = docs[0].page_content
        return result

    def query_csv(self, query, source_name):
        results =  self.db.similarity_search(
                    query=query,
                    k=5,  # Top 2 results
                    filter={"source": source_name}  # Filter based on metadata
                )
        result = ""
        if len(results) > 0:
            result = results[0].page_content
        return result

    def add_knowledge(self, question: str, answer: list):
        knowledge = question + '\nAnswer: '+ '\n'.join(answer)
        self.add_text(convert_to_single_word(question), knowledge)
    