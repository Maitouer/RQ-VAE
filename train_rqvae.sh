CUDA_VISIBLE_DEVICES=0,1
python -m debugpy --listen 55778 --wait-for-client train_rqvae.py