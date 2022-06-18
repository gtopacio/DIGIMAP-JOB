import os
import glob
import datetime

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

def generateURL(bucket, blob_name):
    blob = bucket.blob(blob_name)
    url = blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(minutes=1380),
        method="GET",
    )
    return url
