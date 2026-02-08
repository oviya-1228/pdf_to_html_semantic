import fitz  # PyMuPDF
import os
from typing import List, Dict, Any


def extract_layout_from_pdf(pdf_path: str, task_id: str = None) -> List[Dict[str, Any]]:
    """
    Extracts deterministic layout information from a PDF using PyMuPDF.
    Includes text, images, and vector drawings (lines, rects).
    """

    doc = fitz.open(pdf_path)
    layout_data = []

    # Image directory
    images_base_path = "app/static/images"
    if task_id:
        task_images_dir = os.path.join(images_base_path, task_id)
        os.makedirs(task_images_dir, exist_ok=True)

    # ---------------- SAFE HELPERS ---------------- #

    def safe_point(p):
        if hasattr(p, "x"):
            return {"x": p.x, "y": p.y}
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            return {"x": p[0], "y": p[1]}
        if isinstance(p, dict):
            return {"x": p.get("x", 0), "y": p.get("y", 0)}
        return {"x": 0, "y": 0}

    def safe_rect(r):
        """
        ALWAYS returns [x0, y0, x1, y1]
        Handles fitz.Rect, dict, tuple/list safely
        """
        if hasattr(r, "x0"):
            return [r.x0, r.y0, r.x1, r.y1]
        if isinstance(r, dict):
            return [
                r.get("x0", 0),
                r.get("y0", 0),
                r.get("x1", 0),
                r.get("y1", 0),
            ]
        if isinstance(r, (list, tuple)) and len(r) >= 4:
            return list(r[:4])
        return [0, 0, 0, 0]

    # ---------------- MAIN LOOP ---------------- #

    for page_num, page in enumerate(doc):
        width, height = page.rect.width, page.rect.height

        raw_dict = page.get_text("dict")
        page_blocks = []

        for block in raw_dict.get("blocks", []):
            # Safe extraction of common fields (force defaults if None)
            b_type = block.get("type", -1)
            b_bbox = block.get("bbox")
            if not b_bbox: b_bbox = [0, 0, 0, 0]
            
            block_data = {
                "type": b_type,
                "bbox": b_bbox,
                "number": block.get("number", -1),
            }

            # ---------- TEXT BLOCK ----------
            if b_type == 0:
                lines = []
                for line in block.get("lines", []):
                    spans = []
                    for span in line.get("spans", []):
                        s_bbox = span.get("bbox")
                        if not s_bbox: s_bbox = [0, 0, 0, 0]
                        
                        spans.append({
                            "text": span.get("text", ""),
                            "bbox": s_bbox,
                            "size": span.get("size", 0),
                            "font": span.get("font", ""),
                            "color": span.get("color", 0),
                            "flags": span.get("flags", 0),
                            "origin": span.get("origin", [0, 0]),
                        })
                    
                    l_bbox = line.get("bbox")
                    if not l_bbox: l_bbox = [0, 0, 0, 0]

                    lines.append({
                        "bbox": l_bbox,
                        "wmode": line.get("wmode", 0),
                        "dir": line.get("dir", [1, 0]),
                        "spans": spans,
                    })
                block_data["lines"] = lines

            # ---------- IMAGE BLOCK ----------
            elif b_type == 1:
                image_rel_path = ""
                if task_id and "image" in block:
                    image_filename = f"p{page_num}_img{block.get('number',0)}.png"
                    image_path = os.path.join(task_images_dir, image_filename)
                    try:
                        with open(image_path, "wb") as f:
                            f.write(block["image"])
                        image_rel_path = f"/static/images/{task_id}/{image_filename}"
                    except Exception as e:
                        print("Image save failed:", e)

                block_data["image_info"] = {
                    "src": image_rel_path,
                    "bbox": b_bbox,
                    "width": block.get("width", 0),
                    "height": block.get("height", 0),
                    "ext": block.get("ext", ""),
                }

            page_blocks.append(block_data)

        # ---------- DRAWINGS / VECTORS ----------
        raw_drawings = page.get_drawings()
        clean_drawings = []

        for draw in raw_drawings:
            clean_items = []
            for item in draw.get("items", []):
                if not item: continue
                t = item[0]

                if t == "l":  # line
                    clean_items.append(
                        ("l", safe_point(item[1]), safe_point(item[2]))
                    )

                elif t == "re":  # rectangle
                    rect = safe_rect(item[1])
                    clean_items.append(
                        ("re", {"x0": rect[0], "y0": rect[1], "x1": rect[2], "y1": rect[3]})
                    )

                elif t == "c":  # curve
                    clean_items.append(
                        ("c",
                         safe_point(item[1]),
                         safe_point(item[2]),
                         safe_point(item[3]),
                         safe_point(item[4]))
                    )

            clean_drawings.append({
                "items": clean_items,
                "color": draw.get("color"),
                "fill": draw.get("fill"),
                "width": draw.get("width", 1),
                "rect": safe_rect(draw.get("rect")),
            })

        layout_data.append({
            "page": page_num + 1,
            "width": width,
            "height": height,
            "blocks": page_blocks,
            "drawings": clean_drawings,
        })

    doc.close()
    return layout_data


def validate_pdf_constraints(pdf_path: str, max_pages: int = 50, max_size_mb: int = 100) -> bool:
    """
    Validates PDF constraints safely.
    """
    size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ValueError(f"File size {size_mb:.2f}MB exceeds limit")

    try:
        doc = fitz.open(pdf_path)
        if doc.page_count > max_pages:
            raise ValueError(f"Page count {doc.page_count} exceeds limit")
        doc.close()
    except Exception:
        raise ValueError("Invalid or corrupt PDF")

    return True
