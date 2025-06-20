import sys
import time
import math
import uuid
import random
import logging
import hashlib
import warnings
import json
from faker import Faker
from elasticsearch import Elasticsearch
from urllib3.exceptions import InsecureRequestWarning
from faker.providers.geo import Provider as GeoProvider

# Ignore SSL cert warning for dev
warnings.simplefilter('ignore', InsecureRequestWarning)

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Faker setup
fake = Faker()
fake.add_provider(GeoProvider)

# Cache for consistent entities
host_cache = {}
client_cache = {}
merchant_cache = {}

# ----- Helper Functions -----

def generate_consistent_host(host_id):
    seed = int(hashlib.md5(str(host_id).encode()).hexdigest(), 16) % (10**8)
    random.seed(seed)
    domain = random.choice(["example.com", "test.net", "company.co.id"])
    hostname = f"{host_id.replace('-', '').lower()}.{domain}"
    return {
        "host_id": host_id,
        "hostname": hostname,
        "ip_address": fake.ipv4_private(),
        "domain": domain,
        "os": random.choice(["Windows Server", "Ubuntu", "CentOS"])
    }

def generate_consistent_client(client_id):
    seed = int(hashlib.md5(str(client_id).encode()).hexdigest(), 16) % (10**8)
    random.seed(seed)
    lat, lon, city, country_code, timezone = fake.location_on_land()
    return {
        "client_id": client_id,
        "username": fake.user_name(),
        "ip_address": fake.ipv4_public(),
        "device_type": random.choice(["Desktop", "Mobile"]),
        "location": {
            "lat": float(lat),
            "lon": float(lon)
        },
        "geo_info": {
            "city": city,
            "country_code": country_code,
            "timezone": timezone
        }
    }

def generate_consistent_merchant(merchant_id):
    seed = int(hashlib.md5(str(merchant_id).encode()).hexdigest(), 16) % (10**8)
    random.seed(seed)
    lat, lon, city, country_code, timezone = fake.location_on_land()
    return {
        "merchant_id": merchant_id,
        "name": fake.company(),
        "type": random.choice([
            "GROCERY", "RESTAURANT", "RETAIL", "UTILITIES", "ENTERTAINMENT",
            "TRAVEL", "HEALTHCARE", "EDUCATION", "TRANSPORTATION", "ONLINE_SERVICES"
        ]),
        "location": {
            "lat": float(lat),
            "lon": float(lon)
        },
        "geo_info": {
            "city": city,
            "country_code": country_code,
            "timezone": timezone
        }
    }

# ----- Document Generators -----

def generate_transaction():
    merchant_id = f"merchant-{random.randint(1, 200):03d}"
    if merchant_id not in merchant_cache:
        merchant_cache[merchant_id] = generate_consistent_merchant(merchant_id)
    merchant = merchant_cache[merchant_id]
    return {
        "merchant_id": merchant_id,
        "@timestamp": fake.date_time_this_year().isoformat(),
        "account_number": fake.credit_card_number(),
        "transaction_amount": round(random.uniform(1.0, 1000.0), 2),
        "merchant": {
            "merchant_id": merchant_id,
            "name": merchant["name"],
            "type": merchant["type"],
            "location": merchant["location"],
            "geo_info": merchant["geo_info"]
        },
        "transaction_id": fake.uuid4(),
        "status": random.choice(["COMPLETED", "PENDING", "FAILED"]),
        "payment_method": random.choice(["CREDIT", "DEBIT", "ACH", "WIRE"]),
        "description": fake.sentence(nb_words=6)
    }

def generate_access_log():
    client_id = f"client-{random.randint(1, 20):03d}"
    host_id = f"host-{random.randint(1, 5)}"

    if client_id not in client_cache:
        client_cache[client_id] = generate_consistent_client(client_id)
    if host_id not in host_cache:
        host_cache[host_id] = generate_consistent_host(host_id)

    client = client_cache[client_id]
    host = host_cache[host_id]

    lat = client["location"]["lat"]
    lon = client["location"]["lon"]
    city = client["geo_info"]["city"]
    country_code = client["geo_info"]["country_code"]
    timezone = client["geo_info"]["timezone"]

    return {
        "@timestamp": fake.date_time_this_year().isoformat(),
        "client_id": client_id,
        "client_ip": client["ip_address"],
        "username": client["username"],
        "device_type": client["device_type"],
        "host_id": host_id,
        "host": host["hostname"],
        "host_ip": host["ip_address"],
        "host_domain": host["domain"],
        "host_os": host["os"],
        "method": random.choice(["GET", "POST", "GET", "GET", "GET"]),
        "url": fake.uri_path(),
        "protocol": "HTTP/1.1",
        "status": int(random.choice([200]*6 + [201, 204, 301, 302, 400, 401, 403, 404, 500])),
        "bytes_sent": random.randint(500, 15000),
        "referrer": fake.url(),
        "user_agent": fake.user_agent(),
        "session_id": str(uuid.uuid4()),
        "location": {
            "lat": lat,
            "lon": lon
        },
        "geo_info": {
            "city": city,
            "country_code": country_code,
            "timezone": timezone
        }
    }

# ----- Index Mappings -----

TRANSACTION_MAPPING = {
    "mappings": {
        "properties": {
            "@timestamp": { "type": "date" },
            "account_number": { "type": "keyword" },
            "transaction_amount": { "type": "float" },
            "merchant_id": { "type": "keyword" },
            "merchant": {
                "properties": {
                    "merchant_id": { "type": "keyword" },
                    "name": { "type": "keyword" },
                    "type": { "type": "keyword" },
                    "location": { "type": "geo_point" },
                    "geo_info": {
                        "properties": {
                            "city": { "type": "keyword" },
                            "country_code": { "type": "keyword" },
                            "timezone": { "type": "keyword" }
                        }
                    }
                }
            },
            "transaction_id": { "type": "keyword" },
            "status": { "type": "keyword" },
            "payment_method": { "type": "keyword" },
            "description": { "type": "text" }
        }
    }
}

ACCESS_LOG_MAPPING = {
    "mappings": {
        "properties": {
            "@timestamp": { "type": "date" },
            "client_id": { "type": "keyword" },
            "client_ip": { "type": "ip" },
            "username": { "type": "keyword" },
            "device_type": { "type": "keyword" },
            "host_id": { "type": "keyword" },
            "host": { "type": "keyword" },
            "host_ip": { "type": "ip" },
            "host_domain": { "type": "keyword" },
            "host_os": { "type": "keyword" },
            "method": { "type": "keyword" },
            "url": { "type": "keyword" },
            "protocol": { "type": "keyword" },
            "status": { "type": "integer" },
            "bytes_sent": { "type": "long" },
            "referrer": { "type": "keyword" },
            "user_agent": {
                "type": "text",
                "fields": { "keyword": { "type": "keyword", "ignore_above": 256 } }
            },
            "session_id": { "type": "keyword" },
            "location": { "type": "geo_point" },
            "geo_info": {
                "properties": {
                    "city": { "type": "keyword" },
                    "country_code": { "type": "keyword" },
                    "timezone": { "type": "keyword" }
                }
            }
        }
    }
}

# ----- Core Logic -----

def calculate_total_docs(size_mb, doc_kb=1):
    return math.ceil(size_mb * 1024 / doc_kb)

def run_indexing(es_host, es_username, es_password, index_name, size_mb, data_type):
    logger.info("Connecting to Elasticsearch...")
    es = Elasticsearch(es_host, basic_auth=(es_username, es_password), verify_certs=False)
    es.info()

    if data_type == "access_log":
        generator = generate_access_log
        mapping = ACCESS_LOG_MAPPING
    else:
        generator = generate_transaction
        mapping = TRANSACTION_MAPPING

    if not es.indices.exists(index=index_name):
        es.indices.create(index=index_name, body=mapping)
        logger.info(f"Index '{index_name}' created.")
    else:
        logger.info(f"Index '{index_name}' already exists.")

    total_docs = calculate_total_docs(size_mb)
    batch_size = 1000
    docs_indexed = 0

    for i in range(0, total_docs, batch_size):
        batch = []
        for _ in range(min(batch_size, total_docs - i)):
            batch.append({ "index": { "_index": index_name } })
            batch.append(generator())

        response = es.bulk(operations=batch)
        if response.get("errors"):
            logger.warning("Some documents failed to index.")
            for item in response["items"]:
                if item["index"].get("error"):
                    logger.error(f"Error: {item['index']['error']}")

        docs_indexed += len(batch) // 2
        logger.info(f"Indexed {docs_indexed} / {total_docs}")
        time.sleep(0.05)

    # Save metadata to JSON files if applicable
    if data_type == "access_log":
        with open("hosts.json", "w") as f:
            json.dump(list(host_cache.values()), f, indent=2)
        with open("clients.json", "w") as f:
            json.dump(list(client_cache.values()), f, indent=2)
        logger.info("Saved hosts.json and clients.json")
    elif data_type == "transaction":
        with open("merchants.json", "w") as f:
            json.dump(list(merchant_cache.values()), f, indent=2)
        logger.info("Saved merchants.json")

    logger.info("Data indexing complete.")

# ----- Entry Point -----

if __name__ == "__main__":
    if len(sys.argv) != 7:
        print("Usage: python script_executor.py <es_host> <username> <password> <index> <size_mb> <data_type>")
        sys.exit(1)

    es_host, username, password, index, size_mb, data_type = sys.argv[1:]
    run_indexing(es_host, username, password, index, int(size_mb), data_type)
