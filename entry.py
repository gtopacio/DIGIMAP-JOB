import os
import boto3
import logging
import glob
import botocore.exceptions as ClientError
import argparse

import firebase_admin
from firebase_admin import firestore 


os.environ["AWS_ACCESS_KEY_ID"] = "AKIAQX7GHQCGXGRUJ7R3"
os.environ["AWS_SECRET_ACCESS_KEY"] = "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"
os.environ["BUCKET_NAME"] = "digimap-s3"


parser = argparse.ArgumentParser()
parser.add_argument("--name", action="store_true", help="Runs the image quilting algorithm that uses randomly generates a texture from a static image")
parser.add_argument("--visualize", action="store_true", help="Runs the image quilting algorithm that uses randomly generates a texture from a static image")
parser.add_argument("--image", type=str, default="pattern.png", help="File path of the source texture")
parser.add_argument("--output", type=str, default="generated_texture.png", help="File path where the generated texture will be saved")
parser.add_argument("--block_size", type=int, default=40, help="See 'guide.jpg'")
parser.add_argument("--block_overlap", type=int, default=10, help="See 'guide.jpg'")
parser.add_argument("--output_size", type=int, default=160, help="Size of output image")

args = parser.parse_args()

try:
    cred_obj = firebase_admin.credentials.Certificate("firebase-admin-key.json")
    default_app = firebase_admin.initialize_app(cred_obj, options=None, name="FirestoreDB")
    firestore = firestore.client(app=default_app)

    BUCKET_NAME = os.getenv("BUCKET_NAME")
    OBJECT_NAME = os.getenv("OBJECT_KEY")
    IMAGE_PATH = os.path.join("image", OBJECT_NAME)

    S3 = boto3.client('s3')

    os.makedirs("image", exist_ok=True)
    os.makedirs("video", exist_ok=True)

    S3.download_file(BUCKET_NAME, OBJECT_NAME, IMAGE_PATH)

    os.system("python3 main.py --config argument.yml")

    mypath = os.path.join("video", "*")
    dict = {}
    fileNameNoExt = os.path.splitext(OBJECT_NAME)[0]
    for fileName in glob.glob(mypath):
        baseName = os.path.basename(fileName)
        videoType = baseName.split('_')[1] if len(baseName.split("_")) >= 2 else "empty"
        try:
            S3.upload_file(fileName, BUCKET_NAME, f"outputs/{fileNameNoExt}/{baseName}")
            response = S3.generate_presigned_url('get_object', Params={'Bucket': BUCKET_NAME,'Key': f"outputs/{fileNameNoExt}/{baseName}"}, ExpiresIn=43200)
            dict[videoType] = response
        except ClientError as e:
            logging.error(e)

    firestore.document(f"jobs/{fileNameNoExt}").update({u'links': dict})
except Exception as e:
    print(e)