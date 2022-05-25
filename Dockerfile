FROM pytorch/pytorch:1.9.1-cuda11.1-cudnn8-runtime as baseImage

RUN apt-get update && apt-get install -y xorg libxcb-randr0-dev libxrender-dev libxkbcommon-dev libxkbcommon-x11-0 libavcodec-dev libavformat-dev libswscale-dev
RUN apt-get install -y wget dpkg
RUN wget https://sourceforge.net/projects/virtualgl/files/2.5.2/virtualgl_2.5.2_amd64.deb/download -O virtualgl_2.5.2_amd64.deb
RUN dpkg -i virtualgl*.deb
RUN rm virtualgl*.deb

FROM baseImage

RUN nvidia-xconfig -a --use-display-device=None --virtual=1280x1024
ENV BUCKET_NAME=digimap-s3
ENV OBJECT_KEY=raymund.jpg
ENV DISPLAY=:0.0
RUN apt-get update && apt-get install -y libfontconfig1-dev wget ffmpeg libsm6 libxext6 libxrender-dev mesa-utils-extra libegl1-mesa-dev libgles2-mesa-dev xvfb git python3-pyqt5 libegl1-mesa libglfw3-dev
RUN nohup X &
WORKDIR /3d-photo-inpainting
RUN pip install boto3 firebase_admin Cython
RUN pip install scipy matplotlib scikit-image
RUN pip install networkx cynetworkx
RUN pip install PyQt5
COPY . ./
RUN pip install -r requirements.txt