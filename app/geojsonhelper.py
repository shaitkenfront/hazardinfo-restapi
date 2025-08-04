import boto3
import os
import json

def get_geojson_from_s3(bucket, key):
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(obj["Body"].read())

def load_large_geojson(bucket, key):
    local_path = f"/tmp/{os.path.basename(key)}"

    if not os.path.exists(local_path):  # キャッシュがないときだけDL
        s3 = boto3.client("s3")
        with open(local_path, "wb") as f:
            s3.download_fileobj(bucket, key, f)

    with open(local_path, "r", encoding="utf-8") as f:
        return json.load(f)
    