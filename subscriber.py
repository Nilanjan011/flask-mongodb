from config.redisCache import r

def handle_messages(pubsub):
    for message in pubsub.listen():
        print("message from listen", message)
        if message['type'] == 'message':
            print(f"Message received on channel {message['channel']}: {message['data']}")

def start_subscriber(channel='channel_1'):
    pubsub = r.pubsub()
    pubsub.subscribe(channel)
    print(f"Subscribed to channel: {channel}")
    handle_messages(pubsub)


if __name__ == '__main__':
    start_subscriber()