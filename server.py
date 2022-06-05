import os
import boto3
import json
import firebase_admin
from firebase_admin import firestore, storage
import signal
import sys
from server_utils import clean_folder, generateURL

os.environ["AWS_ACCESS_KEY_ID"] = "AKIAQX7GHQCG6HJXNNND"
os.environ["AWS_SECRET_ACCESS_KEY"] = "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"
os.environ["SQS_QUEUE_URL"] = "https://sqs.ap-southeast-1.amazonaws.com/051485573261/digimap.fifo"

# os.environ["AWS_ACCESS_KEY_ID"] = "AKIAQX7GHQCG6BC5KUUQ"
# os.environ["AWS_SECRET_ACCESS_KEY"] = "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"
# os.environ["SQS_QUEUE_URL"] = "https://sqs.ap-southeast-1.amazonaws.com/051485573261/digimap-dlq.fifo"

os.environ["FIREBASE_BUCKET"] = "digimap-3dp.appspot.com"

SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")
FIREBASE_BUCKET = os.getenv("FIREBASE_BUCKET")

BOOST_BASE = 'BoostingMonocularDepth'
BOOST_INPUTS = 'inputs'
BOOST_OUTPUTS = 'outputs'

if __name__ == "__main__":

    os.makedirs("image", exist_ok=True)

    running = True
    waitTime = 1
    waitTimeCap = 20
    visibilityTimeout = 15*60

    cred_obj = firebase_admin.credentials.Certificate("firebase-admin-key.json")
    default_app = firebase_admin.initialize_app(cred_obj, options=None, name="FirestoreDB")
    firestore = firestore.client(app=default_app)
    bucket = storage.bucket(name=FIREBASE_BUCKET, app=default_app)

    sqs = boto3.client("sqs", region_name="ap-southeast-1")

    def signal_handler(sig, frame):
        global running
        running = False
        print("Program will terminate after finishing the process")

    signal.signal(signal.SIGINT, signal_handler)
    print("Running Renderer")
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
                waitTime = 1
            print(f"No Message Received, Wait Time: {waitTime}")
            continue

        for message in response.get("Messages", []):
            
            try:
                message_body = message["MessageAttributes"]
                receiptHandle = message['ReceiptHandle']
                id = message_body["id"]["StringValue"]
                traj = message_body["traj"]["StringValue"]
                config = os.path.join("arguments", traj+".yml")

                firestore.document(f"jobs/{id}").update({u'status': "PROCESSING", u'message': "Currently being processed"})
                imageBlob = bucket.blob(id+".jpg")
                imageBlob.download_to_filename(os.path.join("image", id+".jpg"))

                print(f"Successfully downloaded {id}")
                print(f"Trajectory: {traj} Config: {config}")

                os.system(f'python main.py --config {config}')

                firestore.document(f"jobs/{id}").update({u'status': "UPLOADING", u'message': "Video being uploaded"})
                videoFileName = id + '_' + traj + '.mp4'
                videoBlob = bucket.blob(videoFileName)
                videoBlob.upload_from_filename(os.path.join("video", videoFileName))

                print(f"Successfully uploaded {videoFileName}")

                signedURL = generateURL(bucket, videoFileName)
                firestore.document(f"jobs/{id}").update({
                    u'status': "FINISHED",
                    u'link': signedURL,
                    u'message': "Successfully generated a 3D Photo"
                })

                print(f"Link: {signedURL}")

                imageBlob.delete()
                print(f"Successfully Deleted Image")
                sqs.delete_message(
                    QueueUrl=SQS_QUEUE_URL,
                    ReceiptHandle=receiptHandle
                )
                print(f"Successfully Deleted Message {receiptHandle}")

            except Exception as e:
                firestore.document(f"jobs/{id}").update({
                    u'status': "FAILED",
                    u'message': str(e)
                })
                print(e)

            finally:
                clean_folder(os.path.join(BOOST_BASE, BOOST_INPUTS))
                clean_folder(os.path.join(BOOST_BASE, BOOST_OUTPUTS))
                clean_folder(os.path.join("image"))
                clean_folder(os.path.join("depth"))
                clean_folder(os.path.join("mesh"))
                clean_folder(os.path.join("video"))

        waitTime = 1