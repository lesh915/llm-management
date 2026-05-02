import requests
import time
import random
from datetime import datetime

class LLMManagementAdapter:
    def __init__(self, agent_id, base_url="http://localhost:47000"):
        self.agent_id = agent_id
        self.base_url = base_url

    def report_call(self, model_id, input_tokens, output_tokens, latency_ms, success=True, error_msg=None):
        metrics = [
            {"name": "latency", "val": latency_ms},
            {"name": "input_tokens", "val": float(input_tokens)},
            {"name": "output_tokens", "val": float(output_tokens)},
            {"name": "success_rate", "val": 1.0 if success else 0.0}
        ]
        
        for m in metrics:
            payload = {
                "agent_id": self.agent_id,
                "model_id": model_id,
                "metric_name": m["name"],
                "value": m["val"]
            }
            try:
                requests.post(f"{self.base_url}/metrics", json=payload, timeout=2)
            except Exception as e:
                print(f"Failed to report metric {m['name']}: {e}")

        if not success and error_msg:
            event = {
                "agent_id": self.agent_id,
                "model_id": model_id,
                "event_type": "llm_failure",
                "severity": "high",
                "description": error_msg
            }
            try:
                requests.post(f"{self.base_url}/events", json=event, timeout=2)
            except Exception as e:
                print(f"Failed to report event: {e}")

def run_test_agent():
    # 등록한 테스트 에이전트 ID
    AGENT_ID = "fb022b2f-c330-4795-8cfb-9f35501d7f83"
    adapter = LLMManagementAdapter(AGENT_ID)
    
    models = ["claude-sonnet-4-6", "gemini-3-flash-preview"]
    
    print(f"Starting test agent: {AGENT_ID}")
    
    for i in range(5):
        model = random.choice(models)
        print(f"[{i+1}/5] Simulating LLM call with {model}...")
        
        # 가상의 지표 생성
        latency = random.uniform(500, 2000)
        in_tokens = random.randint(50, 200)
        out_tokens = random.randint(100, 500)
        success = random.random() > 0.1 # 10% 확률로 실패 시뮬레이션
        
        error = "API connection timeout" if not success else None
        
        adapter.report_call(
            model_id=model,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            latency_ms=latency,
            success=success,
            error_msg=error
        )
        
        time.sleep(1)

    print("Test agent execution completed.")

if __name__ == "__main__":
    run_test_agent()
