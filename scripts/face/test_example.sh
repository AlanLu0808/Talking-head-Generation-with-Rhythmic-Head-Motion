# Copyright (c) 2019, NVIDIA Corporation. All rights reserved.
#
# This work is made available
# under the Nvidia Source Code License (1-way Commercial).
# To view a copy of this license, visit
# https://nvlabs.github.io/few-shot-vid2vid/License.txt

test_model_8(){
    CUDA_VISIBLE_DEVICES=$1 python test_example.py --name $2 \
    --dataset_mode facefore \
    --adaptive_spade \
    --warp_ref \
    --warp_ani \
    --add_raw_loss \
    --spade_combine \
    --example \
    --n_frames_G 1 \
    --which_epoch $3 \
    --how_many $4 \
    --nThreads 0 \
    --dataroot '/home/cxu-serve/p1/common/voxceleb2' \
    --ref_img_id "0" \
    --n_shot 1 \
    --dataset_name vox
}

test_model_8_linear(){
    CUDA_VISIBLE_DEVICES=$1 python test_example.py --name face8_vox_ani \
    --dataset_mode facefore \
    --adaptive_spade \
    --warp_ref \
    --warp_ani \
    --example \
    --n_frames_G 1 \
    --which_epoch $2 \
    --how_many $3 \
    --nThreads 0 \
    --dataroot '/home/cxu-serve/p1/common/voxceleb2' \
    --ref_img_id "0,10,20,30,40,50,60,70" \
    --n_shot 8 \
    --dataset_name vox
}

test_model_1(){
    CUDA_VISIBLE_DEVICES=$1 python test_example.py --name face8_vox_ani \
    --dataset_mode facefore \
    --adaptive_spade \
    --warp_ref \
    --warp_ani \
    --example \
    --n_frames_G 1 \
    --which_epoch $2 \
    --how_many $3 \
    --nThreads 0 \
    --dataroot '/home/cxu-serve/p1/common/voxceleb2' \
    --ref_img_id "0" \
    --n_shot 1 \
    --dataset_name vox
}

test_model_8_grid(){
    CUDA_VISIBLE_DEVICES=$1 python test_example.py --name face8_grid_ani_retrain_temp \
    --dataset_mode facefore \
    --adaptive_spade \
    --warp_ref \
    --example \
    --n_frames_G 1 \
    --which_epoch $2 \
    --how_many $3 \
    --nThreads 0 \
    --dataroot '/home/cxu-serve/p1/common/grid' \
    --ref_img_id "0" \
    --n_shot 1 \
    --dataset_name grid
}

test_model_8_lrs(){
    CUDA_VISIBLE_DEVICES=$1 python test_example.py --name face8_vox_ani_nonlinear \
    --dataset_mode facefore \
    --adaptive_spade \
    --warp_ref \
    --warp_ani \
    --add_raw_loss \
    --spade_combine \
    --example \
    --n_frames_G 1 \
    --which_epoch $2 \
    --how_many $3 \
    --nThreads 0 \
    --dataroot '/home/cxu-serve/p1/common/lrs3/lrs3_v0.4' \
    --ref_img_id "0" \
    --n_shot 1 \
    --dataset_name lrs \
    --serial_batches
}

test_model_8_crema(){
    CUDA_VISIBLE_DEVICES=$1 python test_example.py --name face8_crema_linear \
    --dataset_mode facefore \
    --adaptive_spade \
    --warp_ref \
    --example \
    --n_frames_G 1 \
    --which_epoch $2 \
    --how_many $3 \
    --nThreads 0 \
    --dataroot '/home/cxu-serve/p1/common/CREMA' \
    --ref_img_id "0" \
    --n_shot 1 \
    --dataset_name crema
}

test_model_8_new(){
    CUDA_VISIBLE_DEVICES=$1 python test_example.py --name $2 \
    --dataset_mode facefore \
    --adaptive_spade \
    --warp_ref \
    --warp_ani \
    --add_raw_loss \
    --spade_combine \
    --example \
    --n_frames_G 1 \
    --which_epoch $3 \
    --how_many $4 \
    --nThreads 0 \
    --dataroot '/home/cxu-serve/p1/common/voxceleb2' \
    --ref_img_id "0" \
    --n_shot 1 \
    --dataset_name vox \
    --use_new
}

test_model_8_continue(){
    CUDA_VISIBLE_DEVICES=$1 python test_example.py --name $2 \
    --dataset_mode facefore \
    --adaptive_spade \
    --warp_ref \
    --warp_ani \
    --add_raw_loss \
    --spade_combine \
    --example \
    --n_frames_G 1 \
    --which_epoch $3 \
    --how_many $4 \
    --nThreads 0 \
    --dataroot '/home/cxu-serve/p1/common/voxceleb2' \
    --ref_img_id "0" \
    --n_shot 1 \
    --dataset_name vox \
    --crop_ref
}

test_model_8_linear 1 latest 200
# test_model_8_grid 3 latest 50
# test_model_8 3 face8_vox_ani_nonlinear latest 50
# test_model_1 3 latest 50
# test_model_8_lrs 2 latest 20
# test_model_8_crema 3 45 50
# test_model_8_new 1 face8_vox_new_nonlinear latest 50
# test_model_8 1 face8_vox_ani_nonlinear_continue 4 50
# test_model_8 1 face8_vox_ani_nonlinear_atten latest 100
# test_model_8_continue 1 face8_vox_ani_nonlinear_continue 11 100