from __future__ import annotations
import os
import json
import boto3
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter()

S3_BUCKET = os.environ.get("S3_BUCKET", "llm-management")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "minioadmin")

def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
    )

class DatasetCreate(BaseModel):
    id: str
    cases: list[dict]

@router.get("")
async def list_datasets():
    s3 = get_s3_client()
    try:
        resp = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix="datasets/")
        datasets = []
        if "Contents" in resp:
            for obj in resp["Contents"]:
                key = obj["Key"]
                if key.endswith(".json"):
                    dataset_id = key.replace("datasets/", "").replace(".json", "")
                    datasets.append({
                        "id": dataset_id,
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"].isoformat()
                    })
        return {"data": datasets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{dataset_id}")
async def get_dataset(dataset_id: str):
    s3 = get_s3_client()
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=f"datasets/{dataset_id}.json")
        data = json.loads(obj["Body"].read())
        return {"data": data}
    except s3.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_dataset(body: DatasetCreate):
    s3 = get_s3_client()
    try:
        key = f"datasets/{body.id}.json"
        content = json.dumps({"cases": body.cases}, ensure_ascii=False)
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=content,
            ContentType="application/json"
        )
        return {"data": {"id": body.id}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(dataset_id: str):
    s3 = get_s3_client()
    try:
        s3.delete_object(Bucket=S3_BUCKET, Key=f"datasets/{dataset_id}.json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
