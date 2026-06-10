from fastapi import FastAPI
from app.routes import analyze
from app.services.analysis import analyze_resume

app = FastAPI()
app.include_router(analyze.router)

@app.get("/")
def root():
    
    return {"message": "Resume AI backend is running"}

@app.get("/test")
def test():
    input = {
    "resume": "I built machine learning models using Python and pandas",
    "job_description": "Looking for Python, machine learning, and SQL experience"
    }
    return analyze_resume(input["resume"], input["job_description"])