import os
import json
import boto3

S3_BUCKET = "llm-management"
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://localhost:9000")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "minioadmin")

def seed_agent_dataset():
    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
    )

    dataset_id = "agent-bench-v1"
    # Note: Anthropic uses 'input_schema', OpenAI uses 'parameters'. 
    # Our adapter usually handles conversion, but let's provide a generic structure.
    tools = [
        {
            "name": "get_stock_price",
            "description": "주식의 현재 가격을 조회합니다.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "주식 심볼 (예: 삼성전자, AAPL)"}
                },
                "required": ["symbol"]
            }
        },
        {
            "name": "search_news",
            "description": "특정 주제에 대한 최신 뉴스를 검색합니다.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "검색어"}
                },
                "required": ["query"]
            }
        }
    ]

    cases = [
        {
            "id": "agent-001",
            "input_messages": [{"role": "user", "content": "삼성전자의 현재 주가를 확인하고, 관련 뉴스를 검색해서 투자 의견을 요약해줘."}],
            "expected_output": "삼성전자",
            "tools": tools
        }
    ]

    key = f"datasets/{dataset_id}.json"
    content = json.dumps({"cases": cases}, ensure_ascii=False)
    
    print(f"Uploading {dataset_id} to S3...")
    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=content,
            ContentType="application/json"
        )
        print(f"Successfully seeded {dataset_id}.")
    except Exception as e:
        print(f"Failed to seed dataset: {e}")

if __name__ == "__main__":
    seed_agent_dataset()
