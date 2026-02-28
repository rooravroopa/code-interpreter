import sys
import traceback
import re
import concurrent.futures
from io import StringIO
from typing import List, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CodeRequest(BaseModel):
    code: str


class CodeResponse(BaseModel):
    error: List[int]
    result: str


SAFE_BUILTINS = {
    "print": print,
    "range": range,
    "len": len,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "abs": abs,
    "min": min,
    "max": max,
    "sum": sum,
}


def _run_code(code: str) -> Dict[str, Any]:
    old_stdout = sys.stdout
    sys.stdout = StringIO()

    try:
        exec(code, {"__builtins__": SAFE_BUILTINS}, {})
        output = sys.stdout.getvalue()
        return {"success": True, "output": output}

    except Exception:
        output = traceback.format_exc()
        return {"success": False, "output": output}

    finally:
        sys.stdout = old_stdout


def execute_python_code(code: str) -> Dict[str, Any]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_code, code)

        try:
            return future.result(timeout=5)
        except concurrent.futures.TimeoutError:
            return {
                "success": False,
                "output": "Execution timed out."
            }

def extract_error_lines(traceback_output: str) -> List[int]:
    """
    Extract only user-code line numbers from traceback.
    Looks specifically for: File "<string>", line X
    """
    matches = re.findall(r'File "<string>", line (\d+)', traceback_output)
    return list(sorted(set(int(m) for m in matches)))



@app.post("/code-interpreter", response_model=CodeResponse)
def code_interpreter(request: CodeRequest):

    execution = execute_python_code(request.code)

    if execution["success"]:
        return {
            "error": [],
            "result": execution["output"],
        }

    error_lines = extract_error_lines(execution["output"])

    return {
        "error": error_lines,
        "result": execution["output"],
    }