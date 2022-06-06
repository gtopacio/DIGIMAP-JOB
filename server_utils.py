import os
import glob
import boto3
import datetime
import firebase_admin
from firebase_admin import firestore, storage
import decouple

FIREBASE_BUCKET = decouple.config("FIREBASE_BUCKET")
SQS_QUEUE_URL = decouple.config("SQS_QUEUE_URL")

BOOST_BASE = 'BoostingMonocularDepth'
BOOST_INPUTS = 'inputs'
BOOST_OUTPUTS = 'outputs'

cred_obj = firebase_admin.credentials.Certificate("firebase-admin-key.json")
default_app = firebase_admin.initialize_app(cred_obj, options=None, name="FirestoreDB")
firestore = firestore.client(app=default_app)
bucket = storage.bucket(name=FIREBASE_BUCKET, app=default_app)

sqs = boto3.client("sqs",
        region_name="ap-southeast-1",
        aws_access_key_id=decouple.config("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=decouple.config("AWS_SECRET_ACCESS_KEY")
    )

def clean_folder(folder, img_exts=['.png', '.jpg', '.npy', '.mp4']):

    for img_ext in img_exts:
        paths_to_check = os.path.join(folder, f'*{img_ext}')
        if len(glob.glob(paths_to_check)) == 0:
            continue
        print(paths_to_check)
        if(os.name is "nt"):
            os.system(f'rd {paths_to_check}')
        else:
            os.system(f'rm {paths_to_check}')
    
    os.system(f'rmdir {folder}')
            

def generateURL(bucket, blob_name):
    blob = bucket.blob(blob_name)
    url = blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(minutes=15),
        method="GET",
    )
    return url

def processMessage(message):
    try:
        message_body = message["MessageAttributes"]
        receiptHandle = message['ReceiptHandle']
        id = message_body["id"]["StringValue"]
        traj = message_body["traj"]["StringValue"]

        VIDEO_DIR = os.path.join("video", id)
        MESH_DIR = os.path.join("mesh", id)
        DEPTH_DIR = os.path.join("depth", id)
        IMAGE_DIR = os.path.join("image", id)
        BOOST_IN_DIR = os.path.join(BOOST_BASE, BOOST_INPUTS, id)
        BOOST_OUT_DIR = os.path.join(BOOST_BASE, BOOST_OUTPUTS, id)

        os.makedirs(IMAGE_DIR, exist_ok=True)
        os.makedirs(VIDEO_DIR, exist_ok=True)
        os.makedirs(MESH_DIR, exist_ok=True)
        os.makedirs(DEPTH_DIR, exist_ok=True)
        os.makedirs(BOOST_IN_DIR, exist_ok=True)
        os.makedirs(BOOST_OUT_DIR, exist_ok=True)

        CONFIG_PATH = os.path.join("arguments", traj+".yml")
        IMAGE_PATH = os.path.join("image", id, id+".jpg")
        
        IMAGE_FILE_NAME = f"{id}.jpg"
        VIDEO_FILE_NAME = f"{id}_{traj}.mp4"

        firestore.document(f"jobs/{id}").update({u'status': "PROCESSING", u'message': "Currently being processed"})
        imageBlob = bucket.blob(IMAGE_FILE_NAME)
        imageBlob.download_to_filename(IMAGE_PATH)

        print(f"Successfully downloaded {id}")
        print(f"Trajectory: {traj} Config: {CONFIG_PATH}")

        os.system(f'python main.py --config {CONFIG_PATH} --src_folder {IMAGE_DIR} --mesh_folder {MESH_DIR} --depth_folder {DEPTH_DIR} --video_folder {VIDEO_DIR} --job_id {id}')

        firestore.document(f"jobs/{id}").update({u'status': "UPLOADING", u'message': "Video being uploaded"})
        videoBlob = bucket.blob(VIDEO_FILE_NAME)
        videoBlob.upload_from_filename(os.path.join(VIDEO_DIR, VIDEO_FILE_NAME))

        print(f"Successfully uploaded {VIDEO_FILE_NAME}")

        signedURL = generateURL(bucket, VIDEO_FILE_NAME)
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
        print(f"Successfully Deleted Message {id}")

    except Exception as e:
        firestore.document(f"jobs/{id}").update({
            u'status': "FAILED",
            u'message': str(e)
        })
        print(e)
        sqs.change_message_visibility(
            QueueUrl=SQS_QUEUE_URL,
            ReceiptHandle=receiptHandle,
            VisibilityTimeout=10
        )
        
    finally:
        clean_folder(BOOST_IN_DIR)
        clean_folder(BOOST_OUT_DIR)
        clean_folder(IMAGE_DIR)
        clean_folder(DEPTH_DIR)
        clean_folder(MESH_DIR)
        clean_folder(VIDEO_DIR)