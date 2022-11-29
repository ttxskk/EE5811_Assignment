import os
import sys
import cv2
import glob
import h5py
import numpy as np
import argparse
import os

os.environ["CDF_LIB"] = "/home/sunqingping/Downloads/cdf38_0-dist-all/cdf38_0-dist/lib"
from spacepy import pycdf
from visualization import show_mesh

def h36m_extract(dataset_path, out_path, protocol=1, extract_img=False):
    # bbox expansion factor
    scaleFactor = 1
    # convert joints to global order
    h36m_idx = [11, 6, 7, 8, 1, 2, 3, 12, 24, 14, 15, 17, 18, 19, 25, 26, 27]
    global_idx = [14, 3, 4, 5, 2, 1, 0, 16, 12, 17, 18, 9, 10, 11, 8, 7, 6]

    # structs we use
    imgnames_, scales_, centers_, parts_, Ss_, Ss_2d, bbox_ = [], [], [], [], [], [], []

    # users in validation set
    user_list = [9, 11]

    # go over each user
    for user_i in user_list:
        user_name = 'S%d' % user_i
        # path with GT bounding boxes
        bbox_path = os.path.join(dataset_path, user_name, 'MySegmentsMat', 'ground_truth_bb')
        # path with GT 3D pose
        pose_path = os.path.join(dataset_path, user_name, 'MyPoseFeatures', 'D3_Positions_mono')
        # path with videos
        vid_path = os.path.join(dataset_path, user_name, 'Videos')
        #
        # kp2d_path = os.path.join(dataset_path,user_name,'MyPoseFeatures','D2_Positions')

        # go over all the sequences of each user
        seq_list = glob.glob(os.path.join(pose_path, '*.cdf'))
        seq_list.sort()
        for seq_i in seq_list:

            # sequence info
            print("seq_i :"+str(seq_i))
            seq_name = seq_i.split('/')[-1]
            action, camera, _ = seq_name.split('.')
            action = action.replace(' ', '_')
            # irrelevant sequences
            if action == '_ALL':
                continue

            # 3D pose file
            poses_3d = pycdf.CDF(seq_i)['Pose'][0]  # 2356 96
            kp2d_path = seq_i.replace('D3_Positions_mono', 'D2_Positions')
            kp2d = pycdf.CDF(kp2d_path)['Pose'][0]
            # bbox file
            bbox_file = os.path.join(bbox_path, seq_name.replace('cdf', 'mat'))
            bbox_h5py = h5py.File(bbox_file)

            # video file
            if extract_img:
                vid_file = os.path.join(vid_path, seq_name.replace('cdf', 'mp4'))
                imgs_path = os.path.join(dataset_path, 'images')
                vidcap = cv2.VideoCapture(vid_file)
                success, image = vidcap.read()

            # go over each frame of the sequence
            for frame_i in range(poses_3d.shape[0]):
                # read video frame
                if extract_img:
                    success, image = vidcap.read()
                    if not success:
                        break

                # check if you can keep this frame
                if frame_i % 5 == 0 and (protocol == 1 or camera == '60457274'):
                    # image name
                    imgname = '%s_%s.%s_%06d.jpg' % (user_name, action, camera, frame_i + 1)

                    # save image
                    if extract_img:
                        img_out = os.path.join(imgs_path, imgname)
                        cv2.imwrite(img_out, image)

                    # read GT bounding box
                    mask = bbox_h5py[bbox_h5py['Masks'][frame_i, 0]].value.T
                    ys, xs = np.where(mask == 1)
                    bbox = np.array([np.min(xs), np.min(ys), np.max(xs) + 1, np.max(ys) + 1])

                    S2d = np.reshape(kp2d[frame_i, :], [-1, 2])
                    S17_2d = S2d[h36m_idx]
                    # S17_2d -= S17_2d[0]  # root-centered
                    S24_2d = np.zeros([24, 3])
                    S24_2d[global_idx, :2] = S17_2d
                    S24_2d[global_idx, 2] = 1

                    # bbox = [min(S17_2d[:, 0]), min(S17_2d[:, 1]),
                    #         max(S17_2d[:, 0]), max(S17_2d[:, 1])]


                    center = [(bbox[2] + bbox[0]) / 2, (bbox[3] + bbox[1]) / 2]
                    scale = scaleFactor*max(bbox[2] - bbox[0], bbox[3] - bbox[1]) / 200.


                    # read GT 3D pose
                    Sall = np.reshape(poses_3d[frame_i, :], [-1, 3]) / 1000.
                    S17 = Sall[h36m_idx]
                    S17 -= S17[0]  # root-centered
                    S24 = np.zeros([24, 4])
                    S24[global_idx, :3] = S17
                    S24[global_idx, 3] = 1
                    # show_mesh(show_V=False, kp3d=S24, show_kp=True, name='24')

                    import config as cfg
                    import visualization as vs
                    img_kp = vs.vis_keypoints(image, S24_2d.transpose(1, 0), kps_lines=cfg.all_24_skeleton)
                    save_path = '/home/sunqingping/mnt/data/graphcnn_data_processed/human3.6_test/human3.6'
                    if not os.path.isdir(save_path):
                        os.makedirs(save_path)
                    cv2.imwrite(os.path.join(save_path, imgname), img_kp)
                    # store data
                    imgnames_.append(os.path.join('images', imgname))
                    centers_.append(center)
                    scales_.append(scale)
                    Ss_.append(S24)
                    Ss_2d.append(S24_2d)
                    bbox_.append(bbox)




    # store the data struct
    extra_path = os.path.join(out_path, 'extras')
    if not os.path.isdir(extra_path):
        os.makedirs(extra_path)
    out_file = os.path.join(extra_path,
                            'h36m_valid_protocol%d.npz' % protocol)
    np.savez(out_file, imgname=imgnames_,
             center=centers_,
             scale=scales_,
             S=Ss_,
             part=Ss_2d,
             bbox=bbox_)


if __name__ == '__main__':
    h36m_extract('/home/sunqingping/mnt/data/Dataset/GraphCMR/human3.6', '../extras/extras', protocol=2, extract_img=True)
