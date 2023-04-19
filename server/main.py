import os
import shutil
import uvicorn
from fastapi import FastAPI, File, HTTPException, Depends, Body, UploadFile, APIRouter, Form, Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
import redis.asyncio as redis
from models.api import (
    DeleteRequest,
    DeleteResponse,
    QueryRequest,
    QueryResponse,
    UpsertRequest,
    UpsertResponse,
)
from models.models import (
    DocumentMetadataFilter,
    Query,
)
from datastore.factory import get_datastore
from services.file import get_document_from_file, count_characters_in_file
from typing import Annotated
from fastapi.middleware.cors import CORSMiddleware
from deployer.SurfaceDeploy import SurfaceDeploy
from fastapi.responses import FileResponse, JSONResponse
import jwt
import time

from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter



bearer_scheme = HTTPBearer()
BEARER_TOKEN = os.environ.get("BEARER_TOKEN")
assert BEARER_TOKEN is not None

# Keys for Redis
TOKENS_KEY="utokens"

# Define rate limiters for each subscription plan
free_limiter = RateLimiter(times=100, seconds=86400)
hobby_limiter = RateLimiter(times=1000, seconds=86400)
standard_limiter = RateLimiter(times=5000, seconds=86400)
unlimited_limiter = RateLimiter(times=1000000, seconds=86400)

async def enforce_rate_limiting(request: Request, plan: str) -> None:
    if plan == "free":
        await free_limiter.__call__(request, None)
    elif plan == "hobby":
        await hobby_limiter.__call__(request, None)
    elif plan == "standard":
        await standard_limiter.__call__(request, None)
    elif plan == "unlimited":
        await unlimited_limiter.__call__(request, None)
    else:
        raise HTTPException(status_code=401, detail="Invalid subscription plan")


def validate_token(credentials):
    try:
        secret = "3efdd8b59a11a31d912c6c4c1657607dfc994b1c92eaf9a021551774eb24bc00"
        decoded = jwt.decode(credentials.credentials, secret, algorithms=["HS256"])
        print("=====================*****************========>", decoded)
        return {"user_id": decoded["user"], "plan": decoded["plan"], "plugin_id": decoded['plugin'], "subdomain": decoded['subdomain']}
    except jwt.InvalidSignatureError:
        # raise HTTPException(status_code=401, detail="Invalid or missing token")
        return{"user_id": None, "plan": None}
    except jwt.DecodeError:
        # raise HTTPException(status_code=401, detail="Invalid or missing token")
        return{"user_id": None, "plan": None}
    except jwt.ExpiredSignatureError:
        # raise HTTPException(status_code=401, detail="Token has expired")
        return{"user_id": None, "plan": None}

app = FastAPI()
# app.mount("/.well-known", StaticFiles(directory=".well-known"), name="static")

origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "https://mygptplugin.com",
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
# sub_app = FastAPI(
#     title="Retrieval Plugin API",
#     description="A retrieval API for querying and filtering documents based on natural language queries and metadata",
#     version="1.0.0",
#     servers=[{"url": "https://your-app-url.com"}],
#     dependencies=[Depends(validate_token)],
# )

# app.mount("/sub", sub_app)

@app.post(
    "/upsert-file",
    response_model=UpsertResponse,
)
async def upsert_file(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
):
    decoded = validate_token(credentials)
    user_id = decoded["user_id"]
    plugin_id = decoded["plugin_id"]
    user_plan = decoded["plan"]

    if user_id == None:
        raise HTTPException(status_code=401, detail="Invalid or missing token")

    # Check if Characters count is exceeded for current plugin
    prev_chat_count = await r.get(f"{user_id}:{plugin_id}:chars_count")
    prev_chat_count = prev_chat_count or 0
    prev_chat_count = int(prev_chat_count)
    print(prev_chat_count, type(prev_chat_count))

    if prev_chat_count == None:
        r.set(f"{user_id}:{plugin_id}:chars_count", 0)
    if user_plan == "free" and prev_chat_count > 400000:
        raise HTTPException(status_code=422, detail="You have exceeded the character limit for the free plan. The maximum allowed character limit is 400000.")
    elif user_plan == "hobby" and prev_chat_count > 7000000:
        raise HTTPException(status_code=422, detail="You have exceeded the character limit for the hobby plan. The maximum allowed character limit is 7000000.")
    elif user_plan == "standard" and prev_chat_count > 10000000:
        raise HTTPException(status_code=422, detail="You have exceeded the character limit for the standard plan. The maximum allowed character limit is 10000000.")
    elif user_plan == "unlimited" and prev_chat_count > 20000000:
        raise HTTPException(status_code=422, detail="You have exceeded the character limit for the  plan. The maximum allowed character limit is 20000000.")
   

    # Read the uploaded file
    
    # Count characters in the PDF
    print("Count characters in the PDF")
    start_time = time.time()

    file_stream = await file.read()
    mimetype = file.content_type

    doc_chars = await count_characters_in_file(file_stream, mimetype)
    doc_chars = doc_chars or 0

    time_taken = time.time() - start_time
    print("===========> Time Taken:", time_taken)
    print("===========> Doc Characters:", doc_chars)
    print("===========> Previous Characters:", prev_chat_count)
    
    total_chars = int(doc_chars) + int(prev_chat_count)

    print("===========> Total Characters:", total_chars)

    await r.incrby(f"{user_id}:{plugin_id}:chars_count", int(doc_chars))

    if user_plan == "free" and total_chars > 400000:
        raise HTTPException(status_code=422, detail="You have exceeded the character limit for the free plan. The maximum allowed character limit is 450000.")
    elif user_plan == "hobby" and total_chars > 7000000:
        raise HTTPException(status_code=422, detail="You have exceeded the character limit for the hobby plan. The maximum allowed character limit is 7000000.")
    elif user_plan == "standard" and total_chars > 10000000:
        raise HTTPException(status_code=422, detail="You have exceeded the character limit for the standard plan. The maximum allowed character limit is 10000000.")
    elif user_plan == "unlimited" and total_chars > 20000000:
        raise HTTPException(status_code=422, detail="You have exceeded the character limit for the  plan. The maximum allowed character limit is 20000000.")


    print(file)
    await file.seek(0)
    document = await get_document_from_file(file_stream, mimetype)

    try:
        ids = await datastore.upsert([document])
        print("========> Document IDS:",ids)
        ids_set = set(ids)
        await r.sadd(f"{user_id}:{plugin_id}:ids", *ids_set)
        
        return UpsertResponse(ids=ids)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail=f"str({e})")


# @app.post(
#     "/upsert",
#     response_model=UpsertResponse,
# )
# async def upsert(
#     request: UpsertRequest = Body(...),
# ):
#     try:
#         ids = await datastore.upsert(request.documents)
#         return UpsertResponse(ids=ids)
#     except Exception as e:
#         print("Error:", e)
#         raise HTTPException(status_code=500, detail="Internal Service Error")


@app.post(
    "/query",
    response_model=QueryResponse,
)
async def query_main(
    request: QueryRequest = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    main_request: Request = None,
):
    decoded = validate_token(credentials)
    user_id = decoded["user_id"]
    plugin_id = decoded["plugin_id"]

    if user_id == None:
        return HTTPException(status_code=401, detail="Invalid or missing token")

    # check for rate limiting
    await enforce_rate_limiting(main_request, decoded["plan"])

    doc_ids = list(await r.smembers(f"{user_id}:{plugin_id}:ids"))

    print("===================> Request Quries:-",request.queries)

    for query in request.queries:
        if query.filter == None:
            query.filter = DocumentMetadataFilter(document_id={"$in":doc_ids})
        else:
            query.filter.document_id = {"$in":doc_ids}
    
    try:
        results = await datastore.query(
            request.queries,
        )
        return QueryResponse(results=results)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


# @sub_app.post(
#     "/query",
#     response_model=QueryResponse,
#     # NOTE: We are describing the shape of the API endpoint input due to a current limitation in parsing arrays of objects from OpenAPI schemas. This will not be necessary in the future.
#     description="Accepts search query objects array each with query and optional filter. Break down complex questions into sub-questions. Refine results by criteria, e.g. time / source, don't do this often. Split queries if ResponseTooLargeError occurs.",
# )
# async def query(
#     request: QueryRequest = Body(...),
# ):
#     try:
#         results = await datastore.query(
#             request.queries,
#         )
#         return QueryResponse(results=results)
#     except Exception as e:
#         print("Error:", e)
#         raise HTTPException(status_code=500, detail="Internal Service Error")


@app.delete(
    "/delete",
    response_model=DeleteResponse,
)
async def delete(
    request: DeleteRequest = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
):
    if not (request.ids or request.filter or request.delete_all):
        raise HTTPException(
            status_code=400,
            detail="One of ids, filter, or delete_all is required",
        )

    decoded = validate_token(credentials)
    user_id = decoded["user_id"]
    plugin_id = decoded["plugin_id"]
    subdomain = decoded["subdomain"]

    if user_id == None:
        return HTTPException(status_code=401, detail="Invalid or missing token")

    try:
        success = await datastore.delete(
            ids=request.ids,
            filter=request.filter,
            delete_all=False,
            # delete_all=request.delete_all,
        )
        deleted = DeleteResponse(success=success)
        if deleted:
            await r.delete(f"{user_id}:{plugin_id}:chars_count")
            # remove from redis
            await r.srem(f"{user_id}:{plugin_id}:ids", *request.ids)
            # remove subdomain directory
            subdomain_dir = "./deps/" + subdomain
            if os.path.exists(subdomain_dir) and os.path.isdir(subdomain_dir):
                shutil.rmtree(subdomain_dir)

        return deleted
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


#======================================================Subdomain======================================================
@app.post("/plugins/create", include_in_schema=False)
async def create_plugin(
    user_id: str = Form(...),
    user_plan: str = Form(...),
    # openai_api_key: str = Form(...),
    name_for_human: str = Form(...),
    name_for_model: str = Form(...),
    description_for_human: str = Form(...),
    description_for_model: str = Form(...),
    contact_email: str = Form(...),
    legal_info_url: str = Form(...),
    openapi_title: str = Form(...),
    openapi_description: str = Form(...), 
    logo: UploadFile = File(None),
):
    item = {
        "user_id": user_id,
        "user_plan": user_plan,
        # "openai_api_key": openai_api_key,
        "name_for_human": name_for_human,
        "name_for_model": name_for_model,
        "description_for_human": description_for_human,
        "description_for_model": description_for_model,
        "contact_email": contact_email,
        "legal_info_url": legal_info_url,
        "openapi_title": openapi_title,
        "openapi_description": openapi_description,
    }

    deployer = SurfaceDeploy(user_id, name_for_human, user_plan)

    tkn = deployer.generate_token(item["user_id"], item["user_plan"])
    # r = get_redis_connection()
    # r.sadd(TOKENS_KEY, tkn)

    if user_plan != "free" and user_plan != "hobby":
        deployer.set_configs(item)
        deployer.upload_logo(logo)

    print("Created New App for ", f"- {user_id}", f"- {user_plan}", {
        "app_url": deployer.subdomain,
        "bearer_token": tkn,
        "plugin_id": deployer.plugin_id,
    })
    return {
        "app_url": deployer.app_url,
        "bearer_token": tkn,
        "plugin_id": deployer.plugin_id,
    }


@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
async def ai_plugin_json(request: Request):
    subdomain = request.headers["Host"].split(".")[0]
    file_path = f"./deps/{subdomain}/.well-known/ai-plugin.json"
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    else:
        return FileResponse("./personalized-retrieval-plugin/.well-known/ai-plugin.json")
        # raise HTTPException(status_code=404, detail="File not found")


@app.get("/.well-known/openapi.yaml", include_in_schema=False)
async def openapi_yaml(request: Request):
    subdomain = request.headers["Host"].split(".")[0]
    file_path = f"./deps/{subdomain}/.well-known/openapi.yaml"
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    else:
        return FileResponse("./personalized-retrieval-plugin/.well-known/openapi.yaml")
        # raise HTTPException(status_code=404, detail="File not found")


@app.get("/.well-known/logo.png", include_in_schema=False)
async def logo_png(request: Request):
    subdomain = request.headers["Host"].split(".")[0]
    file_path = f"./deps/{subdomain}/.well-known/logo.png"
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    else:
        return FileResponse("./personalized-retrieval-plugin/.well-known/logo.png")
        # raise HTTPException(status_code=404, detail="File not found")


#======================================================Subdomain======================================================
async def token_identifier(request: Request):
    bearer_token = request.headers.get("Authorization")
    if bearer_token and bearer_token.startswith("Bearer "):
        return bearer_token[7:]
    return request.client.host


# async def default_identifier(request: Request):
#     bearer_token = request.headers.get("Authorization")
#     if bearer_token and bearer_token.startswith("Bearer "):
#         return bearer_token[7:]
#     return request.client.host

@app.on_event("startup")
async def startup():
    global datastore
    datastore = await get_datastore()
    global r
    r = redis.Redis(host='redis-stack-server', port=6379, db=0, decode_responses=True)
    await FastAPILimiter.init(r, prefix="ratelimiter", identifier=token_identifier)



def start():
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)