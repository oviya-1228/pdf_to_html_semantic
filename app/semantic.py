from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification
import torch
from PIL import Image
import os
from typing import List, Dict, Any

# We will use a pre-trained model for demonstration. 
# In a real scenario, you'd fine-tune on a document dataset.
# For this task, we'll map standard NER/Layout labels to our target schema.
MODEL_ID = "microsoft/layoutlmv3-base" # Or a fine-tuned version if available

# Global cache to prevent reloading model on every request
_MODEL_CACHE = {
    "model": None,
    "processor": None,
    "attempted_load": False
}

class SemanticProcessor:
    def __init__(self):
        if not _MODEL_CACHE["attempted_load"]:
            print("Loading AI Model (Lazy Instantiation)...")
            _MODEL_CACHE["attempted_load"] = True
            try:
                # Try to load the fine-tuned model
                _MODEL_CACHE["model"] = LayoutLMv3ForTokenClassification.from_pretrained("nielsr/layoutlmv3-finetuned-publaynet")
                _MODEL_CACHE["processor"] = LayoutLMv3Processor.from_pretrained("microsoft/layoutlmv3-base", apply_ocr=False)
                # self.id2label = _MODEL_CACHE["model"].config.id2label # Optional: store if needed
                print("Model loaded successfully.")
            except Exception as e:
                print(f"Warning: Could not load fine-tuned model: {e}. Semantic understanding will be limited to heuristics.")
                _MODEL_CACHE["model"] = None
                _MODEL_CACHE["processor"] = None
        
        self.model = _MODEL_CACHE["model"]
        self.processor = _MODEL_CACHE["processor"]

    def classify_blocks(self, layout_data: List[Dict[str, Any]], pdf_images: List[Image.Image] = None) -> List[Dict[str, Any]]:
        """
        Enhances layout_data with semantic labels.
        Input: Intermediate JSON (text + bbox)
        Output: Enhanced JSON with 'label' field (heading, paragraph, etc.)
        """
        
        # If no model, fallback to heuristics (Rule-based) to ensure functionality
        if not self.model:
            return self._heuristic_classification(layout_data)

        # TODO: Implement full inference loop
        # 1. Prepare inputs (image + text + bbox)
        # 2. Forward pass
        # 3. Map tokens to blocks
        
        # For this skeleton, we will use a hybrid approach:
        # We'll use heuristics heavily because raw Transformer inference on CPU for full PDF
        # can be slow and complex to map back to specific PDF characters perfectly without 
        # a lot of alignment code. 
        
        return self._heuristic_classification(layout_data)


    def _heuristic_classification(self, layout_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Improved rule-based semantic classification.
        Uses font size, position, alignment, density, and patterns.
        """

        for page in layout_data:
            blocks = page.get("blocks", [])
            if not blocks:
                continue

            # ---------- GLOBAL PAGE STATS ----------
            font_sizes = []
            y_positions = []

            for block in blocks:
                # Safety check
                if block.get("bbox") is None:
                    continue
                    
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if "size" in span:
                            font_sizes.append(span["size"])
                
                # Safe usage of bbox
                y_positions.append(block["bbox"][1])

            if not font_sizes:
                continue

            mode_font = max(set(font_sizes), key=font_sizes.count)
            max_font = max(font_sizes)
            page_height = page.get("height", 1000)
            page_width = page.get("width", 800)

            # ---------- BLOCK CLASSIFICATION ----------
            for block in blocks:
                text = ""
                sizes = []
                
                # Check safe bbox again
                bbox = block.get("bbox", [0,0,0,0])
                if not bbox: bbox = [0,0,0,0]
                
                x0, y0, x1, y1 = bbox
                block_height = y1 - y0
                block_width = x1 - x0
                center_x = (x0 + x1) / 2
                center_ratio = abs(center_x - page_width / 2) / page_width

                # IMAGE BLOCK
                if block.get("type") == 1:
                    block["label"] = "image"
                    block["semantic_type"] = "image"
                    continue

                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        sizes.append(span.get("size", mode_font))
                        text += span.get("text", "") + " "

                text = text.strip()
                if not sizes or not text:
                    block["label"] = "unknown"
                    block["semantic_type"] = "unknown"
                    continue

                avg_size = sum(sizes) / len(sizes)
                line_count = len(block.get("lines", []))
                word_count = len(text.split())

                # ---------- RULE 1: MAIN TITLE ----------
                if (
                    avg_size >= max_font * 0.85 and
                    center_ratio < 0.15 and
                    y0 < page_height * 0.25
                ):
                    block["label"] = "heading"
                    block["semantic_type"] = "h1"
                    continue

                # ---------- RULE 2: SECTION HEADINGS ----------
                if (
                    avg_size > mode_font * 1.4 and
                    word_count <= 10 and
                    block_height < page_height * 0.08
                ):
                    block["label"] = "heading"
                    block["semantic_type"] = "h2"
                    continue

                # ---------- RULE 3: SUB-HEADINGS ----------
                if (
                    avg_size > mode_font * 1.2 and
                    avg_size <= mode_font * 1.4 and
                    word_count <= 15
                ):
                    block["label"] = "heading"
                    block["semantic_type"] = "h3"
                    continue

                # ---------- RULE 4: TABLE / METADATA BLOCK ----------
                if (
                    word_count > 5 and
                    line_count >= 4 and
                    block_width > page_width * 0.6 and
                    avg_size <= mode_font * 1.05
                ):
                    block["label"] = "table"
                    block["semantic_type"] = "table"
                    continue

                # ---------- RULE 5: LIST ITEMS ----------
                if text.lstrip().startswith(("•", "-", "–", "1.", "2.", "3.")):
                    block["label"] = "list_item"
                    block["semantic_type"] = "li"
                    continue

                # ---------- RULE 6: FOOTNOTES / CAPTIONS ----------
                if (
                    avg_size < mode_font * 0.85 and
                    y0 > page_height * 0.8
                ):
                    block["label"] = "footnote"
                    block["semantic_type"] = "small"
                    continue

                # ---------- RULE 7: NORMAL PARAGRAPH ----------
                block["label"] = "paragraph"
                block["semantic_type"] = "p"

        return layout_data
