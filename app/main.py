from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
import uvicorn
import os
import shutil
import uuid
import json
from app.parser import extract_layout_from_pdf, validate_pdf_constraints

app = FastAPI(title="PDF Semantic Converter")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

DATA_DIR = "data"
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
INTERMEDIATE_DIR = os.path.join(DATA_DIR, "intermediate")
RESULTS_DIR = os.path.join(DATA_DIR, "results")

for d in [UPLOAD_DIR, INTERMEDIATE_DIR, RESULTS_DIR]:
    os.makedirs(d, exist_ok=True)

# In-memory status store (replace with DB/Redis in prod)
TASK_STATUS = {}

def process_pdf_task(task_id: str, file_path: str):
    try:
        TASK_STATUS[task_id] = {"status": "processing", "step": "validating"}
        
        # Ensure image directory exists for this task
        images_dir = os.path.join("app", "static", "images", task_id)
        os.makedirs(images_dir, exist_ok=True)

        # Phase 1: Validation
        validate_pdf_constraints(file_path)
        
        # Phase 2: Parsing
        TASK_STATUS[task_id]["step"] = "parsing"
        # Pass task_id to parser for saving images
        layout_data = extract_layout_from_pdf(file_path, task_id)
        
        # Phase 3: Semantic Analysis
        TASK_STATUS[task_id]["step"] = "analyzing"
        from app.semantic import SemanticProcessor
        processor = SemanticProcessor()
        semantic_data = processor.classify_blocks(layout_data)
        
        # Phase 4: Output Generation
        TASK_STATUS[task_id]["step"] = "generating"
        from app.renderer import renderer
        html_output = renderer.generate_html(semantic_data)
        json_output = renderer.generate_json(semantic_data)
        
        # Save Outputs
        with open(os.path.join(RESULTS_DIR, f"{task_id}.html"), "w", encoding="utf-8") as f:
            f.write(html_output)
        
        with open(os.path.join(RESULTS_DIR, f"{task_id}.json"), "w", encoding="utf-8") as f:
            json.dump(json_output, f, indent=2)

        # Save Intermediate JSON (Updated with semantics)
        intermediate_path = os.path.join(INTERMEDIATE_DIR, f"{task_id}.json")
        with open(intermediate_path, "w", encoding="utf-8") as f:
            json.dump(semantic_data, f, indent=2)
            
        TASK_STATUS[task_id] = {
            "status": "completed", 
            "step": "done", 
            "result_html": f"/results/{task_id}/html",
            "result_json": f"/results/{task_id}/json"
        }
    except Exception as e:
        print(f"Error processing task {task_id}: {e}")
        TASK_STATUS[task_id] = {"status": "failed", "error": str(e)}

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF allowed.")
    
    task_id = str(uuid.uuid4())
    file_location = os.path.join(UPLOAD_DIR, f"{task_id}.pdf")
    
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Start background processing
    TASK_STATUS[task_id] = {"status": "queued"}
    background_tasks.add_task(process_pdf_task, task_id, file_location)
        
    return {"task_id": task_id, "status": "queued", "filename": file.filename}

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    return TASK_STATUS.get(task_id, {"status": "not_found"})

@app.get("/intermediate/{task_id}")
async def get_intermediate(task_id: str):
    path = os.path.join(INTERMEDIATE_DIR, f"{task_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    raise HTTPException(status_code=404, detail="Result not found")

@app.get("/results/{task_id}/html")
async def get_result_html(task_id: str):
    path = os.path.join(RESULTS_DIR, f"{task_id}.html")
    if os.path.exists(path):
        return FileResponse(path, media_type="text/html")
    raise HTTPException(status_code=404, detail="HTML result not found")

@app.get("/results/{task_id}/json")
async def get_result_json(task_id: str):
    path = os.path.join(RESULTS_DIR, f"{task_id}.json")
    if os.path.exists(path):
        return FileResponse(path, media_type="application/json")
    raise HTTPException(status_code=404, detail="JSON result not found")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
