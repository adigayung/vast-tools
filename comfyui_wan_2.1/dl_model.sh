#!/bin/bash

echo "⬇️  Downloading Wan 2.1 I2V base model..."
mkdir -p /workspace/ComfyUI/models/diffusion_models
cd /workspace/ComfyUI/models/diffusion_models
MODEL_NAME="Wan2_1-I2V-14B-720P_fp8_e4m3fn.safetensors"
if [[ ! -f $MODEL_NAME ]]; then
    wget -c "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/$MODEL_NAME"
else
    echo "✅ $MODEL_NAME already exists. Skipping download."
fi

echo "⬇️  Downloading VAE..."
mkdir -p /workspace/ComfyUI/models/vae
cd /workspace/ComfyUI/models/vae
VAE_NAME="wan_2.1_vae.safetensors"
if [[ ! -f $VAE_NAME ]]; then
    wget -c "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/$VAE_NAME"
else
    echo "✅ $VAE_NAME already exists. Skipping download."
fi

echo "⬇️  Downloading CLIP Vision..."
mkdir -p /workspace/ComfyUI/models/clip_vision
cd /workspace/ComfyUI/models/clip_vision
CLIP_NAME="clip_vision_h.safetensors"
if [[ ! -f $CLIP_NAME ]]; then
    wget -c "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/$CLIP_NAME"
else
    echo "✅ $CLIP_NAME already exists. Skipping download."
fi

echo "⬇️  Downloading Text Encoder..."
mkdir -p /workspace/ComfyUI/models/text_encoders
cd /workspace/ComfyUI/models/text_encoders
TEXT_ENCODER_NAME="umt5_xxl_fp8_e4m3fn_scaled.safetensors"
if [[ ! -f $TEXT_ENCODER_NAME ]]; then
    wget -c "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/$TEXT_ENCODER_NAME"
else
    echo "✅ $TEXT_ENCODER_NAME already exists. Skipping download."
fi

echo "✅ Done downloading all Wan 2.1 models!"
