from __future__ import annotations
from dataclasses import dataclass
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@dataclass(frozen=True)
class LlmClientConfig:
    base_url: str
    model: str
    timeout_sec: float
    retry_max: int

class LlmClient:
    def __init__(self, cfg: LlmClientConfig):
        self.llm = ChatOpenAI(
            base_url=cfg.base_url,
            api_key="lm-studio",
            model=cfg.model,
            timeout=cfg.timeout_sec,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    def chat(self, system_prompt: str, pairs: list[tuple[str,str]]) -> str:
        msgs = [SystemMessage(content=system_prompt)]
        for role, content in pairs:
            if role == "user":
                msgs.append(HumanMessage(content=content))
            elif role == "assistant":
                msgs.append(AIMessage(content=content))
        resp = self.llm.invoke(msgs)
        return (resp.content or "").strip()
