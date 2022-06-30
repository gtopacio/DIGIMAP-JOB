# DIGIMAP-JOB
Code that runs in the Renderer Fleet Instances

## Tested Operating Systems
Ubuntu 18.04 LTS<br>
AWS Linux with Deep Learning Base AMI

## Setup Instructions
1. Run **sudo apt-get update**
2. Run **sudo apt-get install -y libfontconfig1-dev wget ffmpeg libsm6 libxext6 libxrender-dev mesa-utils-extra libegl1-mesa-dev libgles2-mesa-dev xvfb git python3-pyqt5 libegl1-mesa libglfw3-dev**
2. Create a Conda Environment by running **conda create -n 3DP python=3.8 anaconda**
3. Run **pip install -r requirements.txt**
4. Run **sudo chmod +x ./download.sh**
5. Run **./download.sh**
6. Create a **.env** file containing these variables:
<br> **AWS_ACCESS_KEY_ID** - access key id of the IAM user with SQS credentials for job posting
<br> **AWS_SECRET_ACCESS_KEY** - secret key of the IAM user with SQS credentials for job posting
<br> **SQS_QUEUE_URL** - URL of the SQS queue to be used for job posting
<br> **FIREBASE_BUCKET** - bucket URI provided by Firebase Storage (ex. gs://my-app.appspot.com)
<br> **FIREBASE_CREDENTIALS_PATH** - path to the json containing the credentials for firebase-admin
7. Run **python server.py**