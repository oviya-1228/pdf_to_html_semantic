from typing import List, Dict, Any
import html

CSS_SCALE = 96.0 / 72.0  # PDF → CSS DPI conversion

class ContentRenderer:

    def generate_html(self, semantic_data: List[Dict[str, Any]]) -> str:
        html_out = []
        html_out.append("<!DOCTYPE html>")
        html_out.append("<html>")
        html_out.append("<head>")
        html_out.append('<meta charset="utf-8">')
        html_out.append('<link rel="stylesheet" href="/static/css/pdf_render.css">')
        html_out.append("</head>")
        html_out.append('<body class="pdf-render-view">')

        for page in semantic_data:
            width_pt = page.get("width", 595)
            height_pt = page.get("height", 842)
            
            page_w = width_pt * CSS_SCALE
            page_h = height_pt * CSS_SCALE

            # PAGE CONTAINER
            html_out.append(
                f'<div class="pdf-page" style="width:{page_w:.2f}px;height:{page_h:.2f}px;">'
            )

            # SVG LAYER (BORDERS / TABLES)
            if page.get("drawings"):
                # Pass original unscaled dimensions for viewBox
                html_out.append(self._render_vectors(page["drawings"], page_w, page_h, width_pt, height_pt))

            for block in page.get("blocks", []):

                # IMAGE BLOCK
                if block.get("type") == 1:
                    img = block.get("image_info", {})
                    if img.get("src"):
                        style = self._abs_style(img["bbox"], image=True)
                        html_out.append(
                            f'<img src="{img["src"]}" class="pdf-image" style="{style}">'
                        )
                    continue

                # TEXT BLOCK
                text = self._extract_text(block)
                if not text.strip():
                    continue

                # Extract font size from first span
                font_size_pt = 11.0 # Default
                try:
                    # deeply nested safe access
                    lines = block.get("lines", [])
                    if lines:
                        spans = lines[0].get("spans", [])
                        if spans:
                            font_size_pt = spans[0].get("size", 11.0)
                except:
                    pass
                
                # Scale font size to CSS pixels
                font_size_px = font_size_pt * CSS_SCALE
                
                style = self._abs_style(block["bbox"])
                # Add font styling
                style += f"font-size:{font_size_px:.1f}px;"

                label = block.get("label", "paragraph")
                sem = block.get("semantic_type", "p")

                if label == "heading":
                    tag = sem if sem in ["h1","h2","h3","h4","h5","h6"] else "h2"
                    inner = f"<{tag}>{html.escape(text)}</{tag}>"
                else:
                    inner = f"<p>{html.escape(text)}</p>"

                html_out.append(
                    f'<div class="text-block" style="{style}">{inner}</div>'
                )

            html_out.append("</div>")  # page

        html_out.append("</body></html>")
        return "\n".join(html_out)

    def generate_json(self, semantic_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Returns the structured data as-is (clean version).
        """
        return {
            "meta": {
                "version": "1.0",
                "generator": "PDF Semantic Converter"
            },
            "pages": semantic_data
        }

    def _abs_style(self, bbox, image=False):
        if not bbox:
            return "display:none;"
        x0, y0, x1, y1 = bbox
        left = x0 * CSS_SCALE
        top = y0 * CSS_SCALE
        width = (x1 - x0) * CSS_SCALE
        
        if image:
            height = (y1 - y0) * CSS_SCALE
            return f"left:{left:.2f}px;top:{top:.2f}px;width:{width:.2f}px;height:{height:.2f}px;"

        # ❗ NO HEIGHT FOR TEXT
        return f"left:{left:.2f}px;top:{top:.2f}px;width:{width:.2f}px;"

    def _extract_text(self, block):
        text = []
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text.append(span["text"])
        return " ".join(text)

    def _render_vectors(self, drawings, w, h, orig_w, orig_h):
        paths = []
        for d in drawings:
            color = d.get("color", (0,0,0))
            if not color: color = (0,0,0)
            
            stroke = f"rgb({int(color[0]*255)},{int(color[1]*255)},{int(color[2]*255)})"
            width = d.get("width", 1)

            d_cmd = ""
            for item in d["items"]:
                if not item: continue
                t = item[0]
                if t == "l":
                    p1, p2 = item[1], item[2]
                    d_cmd += f"M {p1['x']} {p1['y']} L {p2['x']} {p2['y']} "
                elif t == "re":
                    r = item[1]
                    d_cmd += f"M {r['x0']} {r['y0']} L {r['x1']} {r['y0']} L {r['x1']} {r['y1']} L {r['x0']} {r['y1']} Z "
                elif t == "c":
                    p1, p2, p3, p4 = item[1], item[2], item[3], item[4]
                    d_cmd += f"M {p1['x']} {p1['y']} C {p2['x']} {p2['y']} {p3['x']} {p3['y']} {p4['x']} {p4['y']} "

            if d_cmd:
                paths.append(
                    f'<path d="{d_cmd}" stroke="{stroke}" stroke-width="{width}" fill="none"/>'
                )

        # Use viewBox to scale the 72-DPI coordinates (orig_w/h) to the 96-DPI container (w/h)
        return f'<svg class="pdf-vectors" width="{w:.2f}" height="{h:.2f}" viewBox="0 0 {orig_w} {orig_h}">' + "".join(paths) + "</svg>"

renderer = ContentRenderer()
