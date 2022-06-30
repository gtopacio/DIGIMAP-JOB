import os
import boto3
import firebase_admin
from firebase_admin import firestore, storage
import signal
from server_utils import clean_folder, generateURL
import decouple
import torch

SQS_QUEUE_URL = decouple.config("SQS_QUEUE_URL")
FIREBASE_BUCKET = decouple.config("FIREBASE_BUCKET")
FIREBASE_CREDENTIALS_PATH = decouple.config("FIREBASE_CREDENTIALS_PATH")

BOOST_BASE = 'BoostingMonocularDepth'
BOOST_INPUTS = 'inputs'
BOOST_OUTPUTS = 'outputs'

@firestore.transactional
def update_latest(transaction, latest_ref, jobNumber):
    snapshot = latest_ref.get(transaction=transaction)

    if not snapshot:
        transaction.set(latest_ref, {
            u'value': jobNumber
        })
        return

    if snapshot.get(u'value') < jobNumber:
        transaction.update(latest_ref, {
            u'value': jobNumber
        })


if __name__ == "__main__":

    os.makedirs("image", exist_ok=True)

    running = True
    waitTime = 1
    waitTimeCap = 20
    visibilityTimeout = 60*60

    cred_obj = firebase_admin.credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
    default_app = firebase_admin.initialize_app(cred_obj, options=None, name="FirestoreDB")
    firestore = firestore.client(app=default_app)
    bucket = storage.bucket(name=FIREBASE_BUCKET, app=default_app)

    gpu_ext = "_cpu"
    xvfb = "xvfb-run "

    sqs = boto3.client(
        "sqs",
        region_name="ap-southeast-1",
        aws_access_key_id=decouple.config("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=decouple.config("AWS_SECRET_ACCESS_KEY")
    )

    if torch.cuda.is_available():
        gpu_ext = ""
        xvfb = ""
        print("Initializing Torch CUDA")
        torch.cuda.init()
        print("Torch Initialization Finished")

    def signal_handler(sig, frame):
        global running
        running = False
        print("Program will terminate after finishing the process")

    signal.signal(signal.SIGINT, signal_handler)
    print("Renderer now running")
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
            try:
                message_body = message["MessageAttributes"]
                receiptHandle = message['ReceiptHandle']
                id = message_body["id"]["StringValue"]
                traj = message_body["traj"]["StringValue"]
                config = os.path.join("arguments", f"{traj+gpu_ext}.yml")

                jobNumber = firestore.document(f"jobs/{id}").get(u'jobNumber')

                print(f"Job Number {jobNumber}")

                transaction = firestore.transaction()
                latest_ref = firestore.document("shards/latestJob")

                update_latest(transaction=transaction, latest_ref=latest_ref, jobNumber=jobNumber)

                firestore.document(f"jobs/{id}").update({u'status': "PROCESSING", u'message': "Currently being processed"})

                imageBlob = bucket.blob(id+".jpg")
                imageBlob.download_to_filename(os.path.join("image", id+".jpg"))

                print(f"Successfully downloaded {id}")
                print(f"Trajectory: {traj} Config: {config}")

                os.system(f'{xvfb}python main.py --config {config} --job_id {id}')

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

                sqs.delete_message(
                    QueueUrl=SQS_QUEUE_URL,
                    ReceiptHandle=receiptHandle
                )
                print(f"Successfully Deleted Message {receiptHandle}")

                imageBlob.delete()
                print(f"Successfully Deleted Image")

            except Exception as e:
                firestore.document(f"jobs/{id}").update({
                    u'status': "RETRYING",
                    u'message': "Failed to generate a 3D Photo, will retry"
                })
            finally:
                clean_folder(os.path.join(BOOST_BASE, BOOST_INPUTS))
                clean_folder(os.path.join(BOOST_BASE, BOOST_OUTPUTS))
                clean_folder(os.path.join("image"))
                clean_folder(os.path.join("depth"))
                clean_folder(os.path.join("mesh"))
                clean_folder(os.path.join("video"))

        waitTime = 1