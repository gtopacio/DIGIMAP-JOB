sudo apt-get update
sudo apt-get install -y libfontconfig1-dev wget ffmpeg libsm6 libxext6 libxrender-dev mesa-utils-extra libegl1-mesa-dev libgles2-mesa-dev xvfb git python3-pyqt5 libegl1-mesa libglfw3-dev
sudo apt-get install -y wget
wget https://repo.anaconda.com/miniconda/Miniconda3-py37_4.12.0-Linux-x86_64.sh -O ~/miniconda.sh
bash ~/miniconda.sh -b -p $HOME/miniconda
source ~/.bashrc
conda create --name 3DP python=3.7 anaconda
conda activate 3DP
conda install pytorch torchvision torchaudio cudatoolkit=11.3 -c pytorch
pip install Cython
pip install -r requirements.txt
sudo chmod +x ./download.sh
sudo bash ./download.sh