import os
import uvicorn
from fastapi import FastAPI, File, HTTPException, Depends, Body, UploadFile, APIRouter, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles

from models.api import (
    DeleteRequest,
    DeleteResponse,
    QueryRequest,
    QueryResponse,
    UpsertRequest,
    UpsertResponse,
)
from datastore.factory import get_datastore
from services.file import get_document_from_file
from typing import Annotated
from fastapi.middleware.cors import CORSMiddleware
from deployer.SurfaceDeploy import SurfaceDeploy
from fastapi.responses import FileResponse

bearer_scheme = HTTPBearer()
BEARER_TOKEN = os.environ.get("BEARER_TOKEN")
assert BEARER_TOKEN is not None


def validate_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if credentials.scheme != "Bearer" or credentials.credentials != BEARER_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    return credentials


app = FastAPI(dependencies=[Depends(validate_token)])
app.mount("/.well-known", StaticFiles(directory=".well-known"), name="static")


origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Create a sub-application, in order to access just the query endpoint in an OpenAPI schema, found at http://0.0.0.0:8000/sub/openapi.json when the app is running locally
sub_app = FastAPI(
    title="Retrieval Plugin API",
    description="A retrieval API for querying and filtering documents based on natural language queries and metadata",
    version="1.0.0",
    servers=[{"url": "https://your-app-url.com"}],
    dependencies=[Depends(validate_token)],
)
app.mount("/sub", sub_app)


@app.post(
    "/upsert-file",
    response_model=UpsertResponse,
)
async def upsert_file(
    file: UploadFile = File(...),
):
    document = await get_document_from_file(file)

    try:
        ids = await datastore.upsert([document])
        return UpsertResponse(ids=ids)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail=f"str({e})")


@app.post(
    "/upsert",
    response_model=UpsertResponse,
)
async def upsert(
    request: UpsertRequest = Body(...),
):
    try:
        ids = await datastore.upsert(request.documents)
        return UpsertResponse(ids=ids)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.post(
    "/query",
    response_model=QueryResponse,
)
async def query_main(
    request: QueryRequest = Body(...),
):
    try:
        results = await datastore.query(
            request.queries,
        )
        return QueryResponse(results=results)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@sub_app.post(
    "/query",
    response_model=QueryResponse,
    # NOTE: We are describing the shape of the API endpoint input due to a current limitation in parsing arrays of objects from OpenAPI schemas. This will not be necessary in the future.
    description="Accepts search query objects array each with query and optional filter. Break down complex questions into sub-questions. Refine results by criteria, e.g. time / source, don't do this often. Split queries if ResponseTooLargeError occurs.",
)
async def query(
    request: QueryRequest = Body(...),
):
    
    try:
        results = await datastore.query(
            request.queries,
        )
        return QueryResponse(results=results)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.delete(
    "/delete",
    response_model=DeleteResponse,
)
async def delete(
    request: DeleteRequest = Body(...),
):
    if not (request.ids or request.filter or request.delete_all):
        raise HTTPException(
            status_code=400,
            detail="One of ids, filter, or delete_all is required",
        )
    try:
        success = await datastore.delete(
            ids=request.ids,
            filter=request.filter,
            delete_all=request.delete_all,
        )
        return DeleteResponse(success=success)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.on_event("startup")
async def startup():
    global datastore
    datastore = await get_datastore()


#======================================================Subdomain======================================================
@app.post("/create-plugin")
def create_plugin(
    # openai_api_key: Annotated[str, Form(..., max_length=210)],
    user_id: Annotated[str, Form(..., max_length=210)],
    name_for_human: Annotated[str, Form(..., max_length=50)],
    # name_for_model: Annotated[str, Form(..., max_length=50)],
    # description_for_human: Annotated[str, Form(..., max_length=120)],
    # description_for_model: Annotated[str, Form(..., max_length=8000)],
    # contact_email: Annotated[str, Form(..., max_length=120)],
    # legal_info_url: Annotated[str, Form(..., max_length=1000)],
    # openapi_title: Annotated[str, Form(..., max_length=50)],
    # openapi_description: Annotated[str, Form(..., max_length=500)], 
    logo: UploadFile = File(..., max_size=2*1024*1024)
):
    item = {
        "user_id": user_id,
        # "openai_api_key": openai_api_key,
        "name_for_human": name_for_human,
        # "name_for_model": name_for_model,
        # "description_for_human": description_for_human,
        # "description_for_model": description_for_model,
        # "contact_email": contact_email,
        # "legal_info_url": legal_info_url,
        # "openapi_title": openapi_title,
        # "openapi_description": openapi_description,
    }

    deployer = SurfaceDeploy(user_id, name_for_human)
    deployer.set_configs(item)
    deployer.upload_logo(logo)

    return {
        "subdomain": deployer.subdomain
    }



# Create a router for the subdomain
router = APIRouter()

# Define a function to create a new instance of StaticFiles for each subdomain
def get_subdomain_static_files(subdomain: str) -> StaticFiles:
    subdomain_static_dir = "./deps/" + subdomain
    return StaticFiles(directory=str(subdomain_static_dir))

@router.get("/")
async def read_root(subdomain: str):
    return {"message": f"Hello from {subdomain}.zeki.com!"}
# Add a new route for each subdomain that mounts the corresponding StaticFiles instance
@router.get("/{subdomain}/ai-plugin.json")
async def ai_plugin(subdomain: str):
    return get_subdomain_static_files(subdomain).get_response("ai-plugin.json")
# Add a new route for each subdomain that mounts the corresponding StaticFiles instance
@router.get("/{subdomain}/openapi.yaml")
async def openapi_yaml(subdomain: str):
    return get_subdomain_static_files(subdomain).get_response("openapi.yaml")
# Add a new route for each subdomain that mounts the corresponding StaticFiles instance
@router.get("/{subdomain}/logo.png")
async def read_logo(subdomain: str):
    return get_subdomain_static_files(subdomain).get_response("logo.png")


@router.post("/query")
async def query(request: QueryRequest = Body(...)):
    try:
        results = await datastore.query(
            request.queries,
        )
        return QueryResponse(results=results)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")

# Mount the subdomain router on the main application
app.include_router(router, tags=["subdomains"])
#======================================================Subdomain======================================================


def start():
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
