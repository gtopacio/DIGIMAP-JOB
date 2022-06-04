import os
import boto3
import json
import firebase_admin
from firebase_admin import firestore 
import signal

SQS_QUEUE_URL = os.getenv('SQS_QUEUE_URL')

if __name__ == "__main__":

    running = True
    waitTime = 20
    sqs = s3 = boto3.resource('sqs')
    waitTimeCap = 500

    def signal_handler(sig, frame):
        global running
        running = False
        print("Program will terminate after finishing the process")

    signal.signal(signal.SIGINT, signal_handler)

    while running:
        response = sqs.receive_message(
        QueueUrl=SQS_QUEUE_URL,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=waitTime,
        )

        if(len(response.get('Messages', [])) <= 0):
            if waitTime > waitTimeCap:
                waitTime = 20
            else:
                waitTime *= 2
            continue

        for message in response.get("Messages", []):

            message_body = message["Body"]
            receiptHandle = message['ReceiptHandle']
            messageBody = json.loads(message_body)
            print(messageBody.id)

    # Get SQS
    # Download Image
    # Change Firebase State to PROCESSING
    # Run 3DP
    # Change Firebase State to UPLOADING
    # Upload video
    # Get Links
    # Set Links to Firebase
    # Remove Message from SQS
    # Delete Residual Files
