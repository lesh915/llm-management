import asyncio
import time
import uuid
from typing import Any, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from shared_types.models import AgentSession, AgentTurn, ComparisonResult
from .metrics import EvalCase

class AgentRunner:
    def __init__(self, model_id: str, adapter: Any, db: AsyncSession):
        self.model_id = model_id
        self.adapter = adapter
        self.db = db

    async def run_session(self, case: EvalCase) -> Dict[str, Any]:
        """
        Execute a multi-turn agent simulation.
        Returns a dictionary containing turns and metadata.
        """
        messages = case.input_messages.copy()
        turns_data = []
        max_turns = 10
        current_state = {}
        total_in = 0
        total_out = 0

        for i in range(max_turns):
            start_time = time.monotonic()
            
            resp = await self.adapter.complete(
                messages=messages,
                tools=case.tools or None
            )
            
            latency_ms = (time.monotonic() - start_time) * 1000
            content = resp.content
            tool_calls = content if isinstance(content, list) else []
            thought = "" if isinstance(content, list) else content
            
            in_tokens = resp.usage.get("input_tokens", 0)
            out_tokens = resp.usage.get("output_tokens", 0)
            total_in += in_tokens
            total_out += out_tokens

            turn_info = {
                "turn_index": i,
                "thought": thought,
                "action": tool_calls[0] if tool_calls else None,
                "metrics": {
                    "latency_ms": latency_ms,
                    "input_tokens": in_tokens,
                    "output_tokens": out_tokens,
                    "cumulative_tokens": total_in + total_out
                },
                "state_snapshot": current_state.copy()
            }
            
            if tool_calls:
                # Execute ALL tool calls and collect results
                results = []
                for action in tool_calls:
                    observation = self._execute_mock_tool(action)
                    results.append({"id": action.get("id"), "name": action.get("name"), "content": observation})
                    self._update_state(current_state, action, observation)
                
                # Store the first observation for the trace
                turn_info["observation"] = results[0]["content"] if results else None
                
                messages.append(self.adapter.format_assistant_message(thought, tool_calls))
                
                tool_result_msgs = self.adapter.format_tool_results(results)
                if isinstance(tool_result_msgs, list):
                    messages.extend(tool_result_msgs)
                else:
                    messages.append(tool_result_msgs)
            else:
                turn_info["response"] = thought
                turns_data.append(turn_info)
                break
                
            turns_data.append(turn_info)
            
        return {
            "case_id": case.id,
            "turns": turns_data
        }

    def _execute_mock_tool(self, action: Dict) -> str:
        """Simulates environment feedback for MCP tools."""
        name = action.get("name")
        args_raw = action.get("input") or action.get("arguments") or {}
        
        # Parse if args is a JSON string (typical for OpenAI/Gemini)
        args = args_raw
        if isinstance(args_raw, str):
            try:
                import json
                args = json.loads(args_raw)
            except:
                args = {}

        if name == "get_stock_price":
            symbol = args.get("symbol", "UNKNOWN")
            return f"{symbol}의 현재 가격은 85,200원이며, 전일 대비 +1.2% 상승 중입니다."
        
        if name == "search_news":
            query = args.get("query", "")
            return f"'{query}' 관련 최신 뉴스: 반도체 수출 호조로 인한 실적 개선 기대감 상승..."
            
        if name == "get_weather":
            location = args.get("location", "Seoul")
            return f"{location}의 현재 날씨는 맑음, 기온은 22도입니다."

        return f"Tool '{name}' executed, but no mock response defined."

    def _update_state(self, state: Dict, action: Dict, observation: str):
        """Simulates agent memory/state updates."""
        name = action.get("name")
        args_raw = action.get("input") or action.get("arguments") or {}
        args = args_raw
        if isinstance(args_raw, str):
            try:
                import json
                args = json.loads(args_raw)
            except:
                args = {}

        if name == "get_stock_price":
            symbol = args.get("symbol")
            state[f"last_checked_{symbol}"] = observation
        elif name == "search_news":
            state["last_news_summary"] = observation[:50] + "..."
