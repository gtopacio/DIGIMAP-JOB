import numpy as np
import argparse
import os
from functools import partial
import vispy
import scipy.misc as misc
from tqdm import tqdm
import yaml
import time
from mesh import write_ply, read_ply, output_3d_photo
from utils import get_MiDaS_samples, read_MiDaS_depth
import torch
import cv2
import imageio
import copy
from networks import Inpaint_Color_Net, Inpaint_Depth_Net, Inpaint_Edge_Net
from MiDaS.run import run_depth
from boostmonodepth_utils import run_boostmonodepth
from MiDaS.monodepth_net import MonoDepthNet
import MiDaS.MiDaS_utils as MiDaS_utils
from bilateral_filtering import sparse_bilateral_filtering
import firebase_admin
from firebase_admin import firestore
import decouple

FIREBASE_CREDENTIALS_PATH = decouple.config("FIREBASE_CREDENTIALS_PATH")

parser = argparse.ArgumentParser()
parser.add_argument('--config', type=str, default='argument.yml',help='Configure of post processing')
parser.add_argument('--job_id', type=str, required=True,help='Firestore Document ID')
args = parser.parse_args()

config = yaml.safe_load(open(args.config, 'r'))
if config['offscreen_rendering'] is True:
    if torch.cuda.is_available():
        vispy_backend = 'egl'
    else:
        vispy_backend = 'PyQt5'
        #os.environ.pop("QT_QPA_PLATFORM_PLUGIN_PATH")
    vispy.use(app=vispy_backend)

os.makedirs(config['mesh_folder'], exist_ok=True)
os.makedirs(config['video_folder'], exist_ok=True)
os.makedirs(config['depth_folder'], exist_ok=True)
sample_list = get_MiDaS_samples(config['src_folder'], config['depth_folder'], config, config['specific'])
normal_canvas, all_canvas = None, None

if isinstance(config["gpu_ids"], int) and (config["gpu_ids"] >= 0):
    device = config["gpu_ids"]
else:
    device = "cpu"

print(f"running on device {device}")

FIRESTORE_ID = args.job_id
cred_obj = firebase_admin.credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
default_app = firebase_admin.initialize_app(cred_obj, options=None, name="FirestoreDB")
firestore = firestore.client(app=default_app)

firestore.document(f"jobs/{FIRESTORE_ID}").update({u'progress': 0})
firestore.document(f"jobs/{FIRESTORE_ID}").update({u'stage': "Starting..."})

for idx in tqdm(range(len(sample_list))):

    depth = None
    sample = sample_list[idx]
    print("Current Source ==> ", sample['src_pair_name'])
    mesh_fi = os.path.join(config['mesh_folder'], sample['src_pair_name'] +'.ply')
    image = imageio.imread(sample['ref_img_fi'])

    firestore.document(f"jobs/{FIRESTORE_ID}").update({u'progress': 0})
    firestore.document(f"jobs/{FIRESTORE_ID}").update({u'stage': "Running depth extraction..."})


    print(f"Running depth extraction at {time.time()}")
    if config['use_boostmonodepth'] is True:
        run_boostmonodepth(sample['ref_img_fi'], config['src_folder'], config['depth_folder'])
    elif config['require_midas'] is True:
        run_depth([sample['ref_img_fi']], config['src_folder'], config['depth_folder'],
                  config['MiDaS_model_ckpt'], MonoDepthNet, MiDaS_utils, target_w=640)

    firestore.document(f"jobs/{FIRESTORE_ID}").update({u'progress': 10})
    firestore.document(f"jobs/{FIRESTORE_ID}").update({u'stage': "Formatting depth..."})           

    if 'npy' in config['depth_format']:
        config['output_h'], config['output_w'] = np.load(sample['depth_fi']).shape[:2]
    else:
        config['output_h'], config['output_w'] = imageio.imread(sample['depth_fi']).shape[:2]

    firestore.document(f"jobs/{FIRESTORE_ID}").update({u'progress': 20})
    firestore.document(f"jobs/{FIRESTORE_ID}").update({u'stage': "Configuring resolution..."})  

    frac = config['longer_side_len'] / max(config['output_h'], config['output_w'])
    config['output_h'], config['output_w'] = int(config['output_h'] * frac), int(config['output_w'] * frac)
    config['original_h'], config['original_w'] = config['output_h'], config['output_w']

    firestore.document(f"jobs/{FIRESTORE_ID}").update({u'progress': 30})

    if image.ndim == 2:
        image = image[..., None].repeat(3, -1)

    firestore.document(f"jobs/{FIRESTORE_ID}").update({u'progress': 40})
    firestore.document(f"jobs/{FIRESTORE_ID}").update({u'stage': "Detecting color..."})  

    if np.sum(np.abs(image[..., 0] - image[..., 1])) == 0 and np.sum(np.abs(image[..., 1] - image[..., 2])) == 0:
        config['gray_image'] = True
    else:
        config['gray_image'] = False

    firestore.document(f"jobs/{FIRESTORE_ID}").update({u'progress': 50})
    firestore.document(f"jobs/{FIRESTORE_ID}").update({u'stage': "Depth interpolation..."})  

    image = cv2.resize(image, (config['output_w'], config['output_h']), interpolation=cv2.INTER_AREA)
    depth = read_MiDaS_depth(sample['depth_fi'], 3.0, config['output_h'], config['output_w'])
    mean_loc_depth = depth[depth.shape[0]//2, depth.shape[1]//2]

    #end depth extraction

    if not(config['load_ply'] is True and os.path.exists(mesh_fi)):

        firestore.document(f"jobs/{FIRESTORE_ID}").update({u'progress': 60})
        firestore.document(f"jobs/{FIRESTORE_ID}").update({u'stage': "Modelling image..."})  

        vis_photos, vis_depths = sparse_bilateral_filtering(depth.copy(), image.copy(), config, num_iter=config['sparse_iter'], spdb=False)
        depth = vis_depths[-1]
        model = None
        torch.cuda.empty_cache()
        print("Start Running 3D_Photo ...")

        firestore.document(f"jobs/{FIRESTORE_ID}").update({u'progress': 65})
        firestore.document(f"jobs/{FIRESTORE_ID}").update({u'stage': "Loading edge model..."})  

        print(f"Loading edge model at {time.time()}")
        depth_edge_model = Inpaint_Edge_Net(init_weights=True)
        depth_edge_weight = torch.load(config['depth_edge_model_ckpt'],
                                       map_location=torch.device(device))
        depth_edge_model.load_state_dict(depth_edge_weight)
        depth_edge_model = depth_edge_model.to(device)
        depth_edge_model.eval()

        firestore.document(f"jobs/{FIRESTORE_ID}").update({u'progress': 70})
        firestore.document(f"jobs/{FIRESTORE_ID}").update({u'stage': "Loading depth model..."})  

        print(f"Loading depth model at {time.time()}")
        depth_feat_model = Inpaint_Depth_Net()
        depth_feat_weight = torch.load(config['depth_feat_model_ckpt'],
                                       map_location=torch.device(device))
        depth_feat_model.load_state_dict(depth_feat_weight, strict=True)
        depth_feat_model = depth_feat_model.to(device)
        depth_feat_model.eval()
        depth_feat_model = depth_feat_model.to(device)

        firestore.document(f"jobs/{FIRESTORE_ID}").update({u'progress': 75})
        firestore.document(f"jobs/{FIRESTORE_ID}").update({u'stage': "Loading rgb model..."})  

        print(f"Loading rgb model at {time.time()}")
        rgb_model = Inpaint_Color_Net()
        rgb_feat_weight = torch.load(config['rgb_feat_model_ckpt'],
                                     map_location=torch.device(device))
        rgb_model.load_state_dict(rgb_feat_weight)
        rgb_model.eval()
        rgb_model = rgb_model.to(device)
        graph = None

        firestore.document(f"jobs/{FIRESTORE_ID}").update({u'progress': 80})
        firestore.document(f"jobs/{FIRESTORE_ID}").update({u'stage': "Writing depth ply..."})  

        print(f"Writing depth ply (and basically doing everything) at {time.time()}")
        rt_info = write_ply(image,
                              depth,
                              sample['int_mtx'],
                              mesh_fi,
                              config,
                              rgb_model,
                              depth_edge_model,
                              depth_edge_model,
                              depth_feat_model)

        if rt_info is False:
            continue
        rgb_model = None
        color_feat_model = None
        depth_edge_model = None
        depth_feat_model = None
        torch.cuda.empty_cache()

    firestore.document(f"jobs/{FIRESTORE_ID}").update({u'progress': 85})
    firestore.document(f"jobs/{FIRESTORE_ID}").update({u'stage': "Meshing ply..."})  
    
    if config['save_ply'] is True or config['load_ply'] is True:
        verts, colors, faces, Height, Width, hFov, vFov = read_ply(mesh_fi)
    else:
        verts, colors, faces, Height, Width, hFov, vFov = rt_info

    firestore.document(f"jobs/{FIRESTORE_ID}").update({u'progress': 90})
    firestore.document(f"jobs/{FIRESTORE_ID}").update({u'stage': "Making video..."})  

    print(f"Making video at {time.time()}")
    videos_poses, video_basename = copy.deepcopy(sample['tgts_poses']), sample['tgt_name']
    top = (config.get('original_h') // 2 - sample['int_mtx'][1, 2] * config['output_h'])
    left = (config.get('original_w') // 2 - sample['int_mtx'][0, 2] * config['output_w'])
    down, right = top + config['output_h'], left + config['output_w']
    border = [int(xx) for xx in [top, down, left, right]]
    normal_canvas, all_canvas = output_3d_photo(verts.copy(), colors.copy(), faces.copy(), copy.deepcopy(Height), copy.deepcopy(Width), copy.deepcopy(hFov), copy.deepcopy(vFov),
                        copy.deepcopy(sample['tgt_pose']), sample['video_postfix'], copy.deepcopy(sample['ref_pose']), copy.deepcopy(config['video_folder']),
                        image.copy(), copy.deepcopy(sample['int_mtx']), config, image,
                        videos_poses, video_basename, config.get('original_h'), config.get('original_w'), border=border, depth=depth, normal_canvas=normal_canvas, all_canvas=all_canvas,
                        mean_loc_depth=mean_loc_depth)

    firestore.document(f"jobs/{FIRESTORE_ID}").update({u'progress': 100})
    firestore.document(f"jobs/{FIRESTORE_ID}").update({u'stage': "Finishing..."})  
