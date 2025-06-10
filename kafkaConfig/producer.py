from kafka import KafkaProducer
import json


producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')

)


def produceMesg(obj):
    # send msg
    producer.send('my_topic', obj)
    producer.flush()