import os
import boto3
import signal
import psutil
import multiprocessing
import queue
from decouple import config
from server_utils import SQS_QUEUE_URL, processMessage

def worker(input_queue, stop_event):
    while not stop_event.is_set():
        try:
            message = input_queue.get(True, 1)
            input_queue.task_done()
        except queue.Empty:
            continue
        processMessage(message)


if __name__ == "__main__":

    print("Running Renderer")

    os.makedirs("image", exist_ok=True)
    os.makedirs("depth", exist_ok=True)
    os.makedirs("mesh", exist_ok=True)
    os.makedirs("video", exist_ok=True)

    running = True
    waitTime = 1
    waitTimeCap = 20
    visibilityTimeout = 15*60

    sqs = boto3.client("sqs",
        region_name="ap-southeast-1",
        aws_access_key_id=config("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=config("AWS_SECRET_ACCESS_KEY")
    )

    input_queue = multiprocessing.JoinableQueue()
    stop_event = multiprocessing.Event()
    workers = []

    jobMemLimit = 8 * 1000 * 1024 * 1024
    numWorkers = int(psutil.virtual_memory().available / jobMemLimit)

    print("Number of Workers: ", numWorkers)

    for _ in range(numWorkers):
        p = multiprocessing.Process(target=worker, args=(input_queue, stop_event))
        workers.append(p)
        p.start()

    def signal_handler(sig, frame):
        global running
        global stop_event
        running = False
        stop_event.set()
        print("Program will terminate after finishing the process")
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    while running:
        response = sqs.receive_message(
            QueueUrl=SQS_QUEUE_URL,
            AttributeNames=[
                'SentTimestamp'
            ],
            MaxNumberOfMessages=1,
            MessageAttributeNames=[
                'All'
            ],
            VisibilityTimeout=visibilityTimeout,
            WaitTimeSeconds=waitTime
        )

        if(len(response.get('Messages', [])) <= 0):
            waitTime *= 2
            if waitTime > waitTimeCap:
                waitTime = waitTimeCap
            continue

        for message in response.get("Messages", []):
            input_queue.put(message)

        waitTime = 1

    input_queue.join()
    for w in workers:
        w.join()