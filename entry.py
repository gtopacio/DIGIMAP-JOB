import os
import boto3
import logging
import glob
import botocore.exceptions as ClientError

import firebase_admin
from firebase_admin import firestore 

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
except:
    print("Error")