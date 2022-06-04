sudo apt-get update
sudo apt-get update && apt-get install -y libfontconfig1-dev wget ffmpeg libsm6 libxext6 libxrender-dev mesa-utils-extra libegl1-mesa-dev libgles2-mesa-dev xvfb git python3-pyqt5 libegl1-mesa libglfw3-dev
conda create -n 3DP python=3.7 anaconda
conda activate 3DP
pip install -r requirements.txt
conda install pytorch==1.4.0 torchvision==0.5.0 cudatoolkit==10.1.243 -c pytorch
sudo chmod +x ./download.sh
sudo bash ./download.sh