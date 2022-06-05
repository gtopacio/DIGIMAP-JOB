sudo apt-get update
sudo apt-get install -y libfontconfig1-dev wget ffmpeg libsm6 libxext6 libxrender-dev mesa-utils-extra libegl1-mesa-dev libgles2-mesa-dev xvfb git python3-pyqt5 libegl1-mesa libglfw3-dev
sudo apt-get install nodejs
sudo apt-get install npm
sudo npm cache clean -f
sudo npm install -g n
sudo n stable
sudo npm install -g pm2
pip3 install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu113
pip install -r requirements.txt
sudo chmod +x ./download.sh
sudo bash ./download.sh