
# PMOVES MinIO Presign Nodes for ComfyUI
import os, io, json, requests, time, mimetypes
from typing import Tuple, List
from PIL import Image

PRESIGN_URL = os.environ.get("PMOVES_PRESIGN_URL","http://localhost:8088")
PRESIGN_TOKEN = os.environ.get("PMOVES_PRESIGN_TOKEN","")

def _auth_headers():
    return {"Authorization": f"Bearer {PRESIGN_TOKEN}"} if PRESIGN_TOKEN else {}

class PMovesUploadImage:
    """
    Uploads an IMAGE to MinIO using presigned PUT.
    """
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "bucket": ("STRING", {"default":"outputs"}),
                "key_prefix": ("STRING", {"default":"comfy/"}),
                "filename": ("STRING", {"default":"image.png"}),
                "content_type": ("STRING", {"default":"image/png"}),
                "expires": ("INT", {"default": 900, "min":60, "max":604800})
            }
        }
    RETURN_TYPES = ("STRING","STRING")
    RETURN_NAMES = ("s3_uri","presigned_get")
    FUNCTION = "upload"
    CATEGORY = "PMOVES/MinIO"

    def upload(self, image, bucket, key_prefix, filename, content_type, expires):
        # image is a batch; take first frame
        i =  image[0].cpu().numpy()
        # convert from ComfyUI tensor (0..1 RGB) to PIL
        pil = Image.fromarray((i * 255).clip(0,255).astype("uint8"))
        buf = io.BytesIO()
        pil.save(buf, format="PNG" if content_type=="image/png" else "JPEG")
        data = buf.getvalue()

        key = key_prefix + filename
        # Get PUT URL
        rs = requests.post(f"{PRESIGN_URL}/presign/put", json={"bucket":bucket,"key":key,"expires":expires,"content_type":content_type}, headers=_auth_headers(), timeout=10)
        rs.raise_for_status()
        put = rs.json()
        # Upload
        up = requests.put(put["url"], data=data, headers={"Content-Type": content_type}) if content_type else None, timeout=30)
        if up.status_code not in (200,204):
            raise RuntimeError(f"upload failed: {up.status_code}")
        # Get GET URL
        gs = requests.post(f"{PRESIGN_URL}/presign/get", json={"bucket":bucket,"key":key,"expires":expires}, headers=_auth_headers(), timeout=10)
        gs.raise_for_status()
        get = gs.json()
        return (f"s3://{bucket}/{key}", get["url"])

class PMovesUploadFilePath:
    """
    Uploads a file from disk (path) via presigned PUT.
    """
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "file_path": ("STRING",),
                "bucket": ("STRING", {"default":"outputs"}),
                "key": ("STRING", {"default":"comfy/out.bin"}),
                "expires": ("INT", {"default": 900, "min":60, "max":604800})
            }
        }
    RETURN_TYPES = ("STRING","STRING")
    RETURN_NAMES = ("s3_uri","presigned_get")
    FUNCTION = "upload"
    CATEGORY = "PMOVES/MinIO"

    def upload(self, file_path, bucket, key, expires):
        if not os.path.exists(file_path):
            raise ValueError(f"file not found: {file_path}")
        ctype = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        with open(file_path,"rb") as f:
            data = f.read()
        rs = requests.post(f"{PRESIGN_URL}/presign/put", json={"bucket":bucket,"key":key,"expires":expires,"content_type":ctype}, headers=_auth_headers(), timeout=10)
        rs.raise_for_status()
        put = rs.json()
        up = requests.put(put["url"], data=data, headers={"Content-Type": ctype}, timeout=60)
        if up.status_code not in (200,204): raise RuntimeError(f"upload failed: {up.status_code}")
        gs = requests.post(f"{PRESIGN_URL}/presign/get", json={"bucket":bucket,"key":key,"expires":expires}, headers=_auth_headers(), timeout=10)
        gs.raise_for_status()
        get = gs.json()
        return (f"s3://{bucket}/{key}", get["url"])

NODE_CLASS_MAPPINGS = {
    "PMovesUploadImage": PMovesUploadImage,
    "PMovesUploadFilePath": PMovesUploadFilePath,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "PMovesUploadImage": "PMOVES • Upload Image (MinIO)",
    "PMovesUploadFilePath": "PMOVES • Upload File Path (MinIO)",
}
