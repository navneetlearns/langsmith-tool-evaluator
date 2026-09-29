from dotenv import load_dotenv
from langsmith import Client

load_dotenv()

client = Client()

print("Connected successfully!")

datasets = list(client.list_datasets(limit=5))  # type: ignore

for d in datasets:
    print(d.name)  # type: ignore