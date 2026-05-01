import os
import json
import boto3

S3_BUCKET = "llm-management"
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://localhost:9000")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "minioadmin")

def seed_sample_dataset():
    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
    )

    dataset_id = "general-knowledge-v1"
    cases = [
        {
            "id": "gk-001",
            "input_messages": [{"role": "user", "content": "태양계에서 가장 큰 행성은 무엇인가요? 한 단어로 답하세요."}],
            "expected_output": "목성"
        },
        {
            "id": "gk-002",
            "input_messages": [{"role": "user", "content": "임진왜란이 발생한 연도는 언제인가요? 숫자만 답하세요."}],
            "expected_output": "1592"
        },
        {
            "id": "gk-003",
            "input_messages": [{"role": "user", "content": "물(H2O) 한 분자에는 몇 개의 수소 원자가 있습니까? 숫자만 답하세요."}],
            "expected_output": "2"
        },
        {
            "id": "gk-004",
            "input_messages": [{"role": "user", "content": "세계에서 가장 높은 산은 무엇인가요? 한 단어로 답하세요."}],
            "expected_output": "에베레스트"
        },
        {
            "id": "gk-005",
            "input_messages": [{"role": "user", "content": "대한민국의 국화는 무엇인가요? 한 단어로 답하세요."}],
            "expected_output": "무궁화"
        }
    ]

    key = f"datasets/{dataset_id}.json"
    content = json.dumps({"cases": cases}, ensure_ascii=False)
    
    print(f"Uploading {dataset_id} to S3...")
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=content,
        ContentType="application/json"
    )
    print("Successfully seeded sample dataset.")

if __name__ == "__main__":
    seed_sample_dataset()
