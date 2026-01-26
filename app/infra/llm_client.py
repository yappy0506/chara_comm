from __future__ import annotations
from dataclasses import dataclass
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from tenacity import Retrying, stop_after_attempt, wait_exponential, retry_if_exception_type

@dataclass(frozen=True)
class LlmClientConfig:
    base_url: str
    model: str
    timeout_sec: float
    retry_max: int
    temperature: float
    top_p: float
    max_tokens: int
    presence_penalty: float
    frequency_penalty: float

class LlmClient:
    def __init__(self, cfg: LlmClientConfig):
        self.retry_max = cfg.retry_max
        llm_kwargs: dict[str, object] = {
            "base_url": cfg.base_url,
            "api_key": "lm-studio",
            "model": cfg.model,
            "timeout": cfg.timeout_sec,
            "temperature": cfg.temperature,
            "top_p": cfg.top_p,
            "presence_penalty": cfg.presence_penalty,
            "frequency_penalty": cfg.frequency_penalty,
        }
        if cfg.max_tokens > 0:
            llm_kwargs["max_tokens"] = cfg.max_tokens
        self.llm = ChatOpenAI(**llm_kwargs)

    def chat(self, system_prompt: str, pairs: list[tuple[str,str]]) -> str:
        for attempt in Retrying(
            stop=stop_after_attempt(max(1, self.retry_max)),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                msgs = [SystemMessage(content=system_prompt)]
                for role, content in pairs:
                    if role == "user":
                        msgs.append(HumanMessage(content=content))
                    elif role == "assistant":
                        msgs.append(AIMessage(content=content))
                resp = self.llm.invoke(msgs)
                return (resp.content or "").strip()
        return ""
