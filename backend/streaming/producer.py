import os
import json
import time
import random
from kafka import KafkaProducer
import sys
import hashlib

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ingestion.load_nsl_kdd import COLUMN_NAMES, load_dataframe, transform
from graph.geo_reference import get_deterministic_geo

KAFKA_BROKER = "localhost:9092"
DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "ingestion", "data", "KDDTest+.txt")

import argparse

def hash_str(s):
    return hashlib.sha256(s.encode()).hexdigest()[:16]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1000, help="Number of events to send")
    args = parser.parse_args()

    print(f"Starting producer, connecting to {KAFKA_BROKER}...")
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BROKER,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

    df = load_dataframe(DATA_FILE)
    df_live = df.tail(args.count).copy()
    df_live = transform(df_live, split_name="live")
    
    records = df_live.to_dict(orient="records")
    print(f"Streaming {len(records)} events...")
    
    for row in records:
        # Determine host hash to get continent
        # Safely handle missing keys if they got dropped
        dst_host_srv_count = float(row.get('dst_host_srv_count', 0))
        bucket = int(dst_host_srv_count // 25.5)
        
        hash_input = f"{row.get('protocol_type', '')}_{row.get('service', '')}_{bucket}"
        src_host_id = hash_str(hash_input)
        
        geo_data = get_deterministic_geo(src_host_id)
        continent = geo_data['continent'].lower().replace(" ", "")
        
        topic = f"network-events-{continent}"
        
        producer.send(topic, row)
        print(f"Sent event {row['event_id']} to {topic}")
        if args.count > 1:
            time.sleep(1)

if __name__ == "__main__":
    main()
