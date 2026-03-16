import json
import logging
from pathlib import Path
from datetime import datetime
from .store import ConversationStore

log = logging.getLogger(__name__)

class LoRAManager:
    """Manages dataset preparation and training orchestration for local LoRA."""
    
    def __init__(self, export_dir):
        self.export_dir = Path(export_dir) / "datasets"
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.store = ConversationStore()

    def prepare_dataset(self, conv_ids, format="alpaca", output_name=None):
        """Converts selected conversations into a JSONL dataset."""
        dataset = []
        
        for cid in conv_ids:
            conv = self.store.load(cid)
            if not conv: continue
            
            messages = conv.get("messages", [])
            # Simple turn-based pairing (User -> Assistant)
            for i in range(len(messages) - 1):
                user_msg = messages[i]
                asst_msg = messages[i+1]
                
                if user_msg["role"] == "user" and asst_msg["role"] == "assistant":
                    if format == "alpaca":
                        dataset.append({
                            "instruction": user_msg["content"],
                            "input": "",
                            "output": asst_msg["content"]
                        })
                    elif format == "sharegpt":
                        dataset.append({
                            "conversations": [
                                {"from": "human", "value": user_msg["content"]},
                                {"from": "gpt", "value": asst_msg["content"]}
                            ]
                        })

        if not output_name:
            output_name = f"dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
            
        output_path = self.export_dir / output_name
        
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                for entry in dataset:
                    f.write(json.dumps(entry) + "\n")
            
            log.info(f"Exported dataset with {len(dataset)} pairs to {output_path}")
            return str(output_path), len(dataset)
        except Exception as e:
            log.error(f"Failed to export dataset: {e}")
            return None, 0

    def get_training_command(self, model_path, dataset_path, config):
        """Generates a mockup command for local training via unsloth or llama.cpp."""
        # This is a mockup for now
        rank = config.get("rank", 8)
        alpha = config.get("alpha", 16)
        lr = config.get("lr", 2e-4)
        epochs = config.get("epochs", 3)
        
        cmd = f"python -m synapse.scripts.train_lora \\\n"
        cmd += f"  --model {model_path} \\\n"
        cmd += f"  --dataset {dataset_path} \\\n"
        cmd += f"  --rank {rank} --alpha {alpha} --lr {lr} --epochs {epochs}"
        
        return cmd
