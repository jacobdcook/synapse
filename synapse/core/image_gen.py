import json
import logging
import urllib.request
import urllib.error
import base64
import uuid
from pathlib import Path
from datetime import datetime, timezone
from PyQt5.QtCore import QObject, pyqtSignal, QThread

from ..utils.constants import CONFIG_DIR

log = logging.getLogger(__name__)

GEN_DIR = Path.home() / ".local" / "share" / "synapse" / "generated"
GEN_DIR.mkdir(parents=True, exist_ok=True)

class ImageGenWorker(QThread):
    finished = pyqtSignal(dict)  # { "path": str, "prompt": str, "success": bool, "error": str }

    def __init__(self, provider, params):
        super().__init__()
        self.provider = provider
        self.params = params
        self._stop_flag = False

    def run(self):
        try:
            if self.provider == "sd":
                result = self._run_sd()
            elif self.provider == "comfy":
                result = self._run_comfy()
            elif self.provider == "openai":
                result = self._run_openai()
            else:
                result = {"success": False, "error": f"Unknown provider: {self.provider}"}
            
            self.finished.emit(result)
        except Exception as e:
            log.error(f"Image generation error: {e}")
            self.finished.emit({"success": False, "error": str(e)})

    def _run_sd(self):
        """Stable Diffusion A1111/Forge API implementation."""
        url = self.params.get("url", "http://127.0.0.1:7860")
        endpoint = f"{url.rstrip('/')}/sdapi/v1/txt2img"
        
        payload = {
            "prompt": self.params.get("prompt", ""),
            "negative_prompt": self.params.get("negative_prompt", ""),
            "seed": self.params.get("seed", -1),
            "steps": self.params.get("steps", 20),
            "width": self.params.get("width", 512),
            "height": self.params.get("height", 512),
            "cfg_scale": self.params.get("cfg_scale", 7),
            "sampler_name": "Euler a",
        }

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
            images = data.get("images", [])
            if not images:
                return {"success": False, "error": "No images returned from SD API"}
            
            img_data = base64.b64decode(images[0])
            filename = f"sd_{uuid.uuid4().hex[:8]}.png"
            filepath = GEN_DIR / filename
            
            with open(filepath, "wb") as f:
                f.write(img_data)
            
            return {
                "success": True,
                "path": str(filepath),
                "prompt": payload["prompt"],
                "provider": "Stable Diffusion"
            }

    def _run_openai(self):
        """OpenAI DALL-E 3 implementation."""
        api_key = self.params.get("api_key")
        if not api_key:
            return {"success": False, "error": "OpenAI API Key not found in settings. Please add it to the 'Providers' tab."}

        endpoint = "https://api.openai.com/v1/images/generations"
        payload = {
            "model": "dall-e-3",
            "prompt": self.params.get("prompt", ""),
            "n": 1,
            "size": "1024x1024"
        }

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
                img_url = data["data"][0]["url"]
                
                # Download the image
                with urllib.request.urlopen(img_url, timeout=60) as img_resp:
                    img_data = img_resp.read()
                
                filename = f"dalle_{uuid.uuid4().hex[:8]}.png"
                filepath = GEN_DIR / filename
                with open(filepath, "wb") as f:
                    f.write(img_data)
                
                return {
                    "success": True,
                    "path": str(filepath),
                    "prompt": payload["prompt"],
                    "provider": "DALL-E 3"
                }
        except urllib.error.HTTPError as e:
            err_data = e.read().decode()
            try:
                msg = json.loads(err_data)["error"]["message"]
            except:
                msg = str(e)
            return {"success": False, "error": f"OpenAI Error: {msg}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _run_comfy(self):
        """ComfyUI API — builds a minimal txt2img workflow and polls for result."""
        import time
        url = self.params.get("url", "http://127.0.0.1:8188")
        prompt_text = self.params.get("prompt", "")
        neg = self.params.get("negative_prompt", "")
        steps = self.params.get("steps", 20)
        cfg = self.params.get("cfg_scale", 7)
        width = self.params.get("width", 512)
        height = self.params.get("height", 512)
        seed = self.params.get("seed", -1)
        if seed == -1:
            import random
            seed = random.randint(0, 2**32 - 1)

        workflow = {
            "3": {"class_type": "KSampler", "inputs": {
                "seed": seed, "steps": steps, "cfg": cfg,
                "sampler_name": "euler", "scheduler": "normal",
                "denoise": 1.0,
                "model": ["4", 0], "positive": ["6", 0],
                "negative": ["7", 0], "latent_image": ["5", 0]
            }},
            "4": {"class_type": "CheckpointLoaderSimple", "inputs": {
                "ckpt_name": self.params.get("checkpoint", "v1-5-pruned-emaonly.safetensors")
            }},
            "5": {"class_type": "EmptyLatentImage", "inputs": {
                "width": width, "height": height, "batch_size": 1
            }},
            "6": {"class_type": "CLIPTextEncode", "inputs": {
                "text": prompt_text, "clip": ["4", 1]
            }},
            "7": {"class_type": "CLIPTextEncode", "inputs": {
                "text": neg, "clip": ["4", 1]
            }},
            "8": {"class_type": "VAEDecode", "inputs": {
                "samples": ["3", 0], "vae": ["4", 2]
            }},
            "9": {"class_type": "SaveImage", "inputs": {
                "filename_prefix": "synapse", "images": ["8", 0]
            }}
        }

        payload = json.dumps({"prompt": workflow}).encode()
        req = urllib.request.Request(
            f"{url.rstrip('/')}/prompt",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            return {"success": False, "error": "ComfyUI did not return a prompt_id"}

        for _ in range(300):
            if self._stop_flag:
                return {"success": False, "error": "Cancelled"}
            time.sleep(1)
            try:
                hist_req = urllib.request.Request(f"{url.rstrip('/')}/history/{prompt_id}")
                with urllib.request.urlopen(hist_req, timeout=5) as resp:
                    hist = json.loads(resp.read())
                if prompt_id in hist:
                    outputs = hist[prompt_id].get("outputs", {})
                    for node_id, node_out in outputs.items():
                        images = node_out.get("images", [])
                        if images:
                            img_info = images[0]
                            img_url = f"{url.rstrip('/')}/view?filename={img_info['filename']}&subfolder={img_info.get('subfolder', '')}&type={img_info.get('type', 'output')}"
                            img_req = urllib.request.Request(img_url)
                            with urllib.request.urlopen(img_req, timeout=30) as img_resp:
                                img_data = img_resp.read()
                            filename = f"comfy_{uuid.uuid4().hex[:8]}.png"
                            filepath = GEN_DIR / filename
                            with open(filepath, "wb") as f:
                                f.write(img_data)
                            return {"success": True, "path": str(filepath), "prompt": prompt_text, "provider": "ComfyUI"}
                    return {"success": False, "error": "ComfyUI returned no images"}
            except urllib.error.URLError:
                continue

        return {"success": False, "error": "ComfyUI generation timed out (5 min)"}

class ImageGenerator(QObject):
    def __init__(self):
        super().__init__()
        self._workers = []

    def generate(self, provider, params, callback):
        worker = ImageGenWorker(provider, params)
        worker.finished.connect(callback)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._workers.append(worker)
        worker.start()
        return worker

    def _cleanup_worker(self, worker):
        if worker in self._workers:
            self._workers.remove(worker)
