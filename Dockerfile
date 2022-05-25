FROM pytorch/pytorch:1.9.1-cuda11.1-cudnn8-runtime
ENV BUCKET_NAME=digimap-s3
ENV OBJECT_KEY=raymund.jpg
RUN apt-get update && apt-get install -y libfontconfig1-dev wget ffmpeg libsm6 libxext6 libxrender-dev mesa-utils-extra libegl1-mesa-dev libgles2-mesa-dev xvfb git python3-pyqt5 libegl1-mesa libglfw3-dev
WORKDIR /3d-photo-inpainting
RUN pip install boto3 firebase_admin Cython
RUN pip install scipy matplotlib scikit-image
RUN pip install networkx cynetworkx
RUN pip install PyQt5
COPY . ./
RUN pip install -r requirements.txt