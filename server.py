import os
import boto3
import firebase_admin
from firebase_admin import firestore, storage
import signal
from server_utils import clean_folder, generateURL
import decouple
import torch

SQS_QUEUE_URL = decouple.config("SQS_QUEUE_URL")
HP_SQS_QUEUE_URL = decouple.config("HP_SQS_QUEUE_URL")
FIREBASE_BUCKET = decouple.config("FIREBASE_BUCKET")

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

    sqs = boto3.client(
        "sqs",
        region_name="ap-southeast-1",
        aws_access_key_id=decouple.config("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=decouple.config("AWS_SECRET_ACCESS_KEY")
    )

    if torch.cuda.is_available():
        print("Initializing Torch CUDA")
        torch.cuda.init()
        print("Torch Initialization Finished")

    def signal_handler(sig, frame):
        global running
        running = False
        print("Program will terminate after finishing the process")

    signal.signal(signal.SIGINT, signal_handler)
    print("Running Renderer")
    while running:

        high_priority = True
        response = sqs.receive_message(
            QueueUrl=HP_SQS_QUEUE_URL,
            AttributeNames=[
                'SentTimestamp'
            ],
            MaxNumberOfMessages=1,
            MessageAttributeNames=[
                'All'
            ],
            VisibilityTimeout=visibilityTimeout,
            WaitTimeSeconds=waitTime//2
        )

        if(len(response.get('Messages', [])) <= 0):
            high_priority = False
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
                config = os.path.join("arguments", traj+".yml")

                firestore.document(f"jobs/{id}").update({u'status': "PROCESSING", u'message': "Currently being processed"})

                imageBlob = bucket.blob(id+".jpg")
                imageBlob.download_to_filename(os.path.join("image", id+".jpg"))

                sqs.delete_message(
                    QueueUrl=SQS_QUEUE_URL,
                    ReceiptHandle=receiptHandle
                )
                print(f"Successfully Deleted Message {receiptHandle}")
                print(f"Successfully downloaded {id}")
                print(f"Trajectory: {traj} Config: {config}")

                os.system(f'python main.py --config {config} --job_id {id}')

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

            except Exception as e:
                if not high_priority:
                    firestore.document(f"jobs/{id}").update({
                        u'status': "RETRYING",
                        u'message': "Failed to generate a 3D Photo, will retry"
                    })
                    response = sqs.send_message(
                        QueueUrl=HP_SQS_QUEUE_URL,
                        DelaySeconds=10,
                        MessageAttributes={
                            'id': {
                            'StringValue': id,
                            'DataType': 'String'
                            },
                            'traj': {
                            'StringValue': traj,
                            'DataType': 'String'
                            }
                        },
                        MessageBody=(
                            'Job'
                        )
                    )
                else:
                    firestore.document(f"jobs/{id}").update({
                        u'status': "FAILED",
                        u'message': "Failed to generate a 3D Photo"
                    })
                    imageBlob = bucket.blob(id+".jpg")
                    imageBlob.delete()

            finally:
                clean_folder(os.path.join(BOOST_BASE, BOOST_INPUTS))
                clean_folder(os.path.join(BOOST_BASE, BOOST_OUTPUTS))
                clean_folder(os.path.join("image"))
                clean_folder(os.path.join("depth"))
                clean_folder(os.path.join("mesh"))
                clean_folder(os.path.join("video"))

        waitTime = 1