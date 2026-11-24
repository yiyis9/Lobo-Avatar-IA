import json
import queue
import threading


_lock = threading.Lock()
_subscribers: set[queue.Queue[str]] = set()


def subscribe_contact_events() -> queue.Queue[str]:
    subscriber: queue.Queue[str] = queue.Queue(maxsize=32)
    with _lock:
        _subscribers.add(subscriber)
    return subscriber


def unsubscribe_contact_events(subscriber: queue.Queue[str]) -> None:
    with _lock:
        _subscribers.discard(subscriber)


def publish_new_contact(message_id: int, name: str) -> None:
    event = json.dumps({"id": message_id, "nombre": name}, ensure_ascii=False)
    with _lock:
        subscribers = tuple(_subscribers)
    for subscriber in subscribers:
        try:
            subscriber.put_nowait(event)
        except queue.Full:
            try:
                subscriber.get_nowait()
            except queue.Empty:
                pass
            try:
                subscriber.put_nowait(event)
            except queue.Full:
                pass
