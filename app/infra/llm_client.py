from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.domain.emotion import normalize_emotion_state
from app.domain.models import StructuredReply


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

    def _invoke(self, msgs: list[Any]) -> str:
        for attempt in Retrying(
            stop=stop_after_attempt(max(1, self.retry_max)),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                resp = self.llm.invoke(msgs)
                return (resp.content or "").strip()
        return ""

    def chat(self, system_prompt: str, pairs: list[tuple[str, str]]) -> str:
        msgs = [SystemMessage(content=system_prompt)]
        for role, content in pairs:
            if role == "user":
                msgs.append(HumanMessage(content=content))
            elif role == "assistant":
                msgs.append(AIMessage(content=content))
        return self._invoke(msgs)

    def chat_with_emotion(
        self,
        system_prompt: str,
        pairs: list[tuple[str, str]],
        emotion: dict[str, int],
    ) -> StructuredReply:
        format_rule = (
            "\n\n【Emotion Engine】\n"
            "- 入力は必ずJSONのみ（下記Input schema準拠）。\n"
            "- 出力は必ずJSONのみ（下記Output schema準拠）。\n"
            "- 現在のemotionは0-99の整数で扱う。\n"
            "- 応答を作る前にemotionを会話文脈に沿って更新する。\n"
            "- 感情は以下の傾向で更新する（重要）。\n"
            "  - Joy: 称賛・感謝・成功・安心材料で上げ、失敗・拒絶・攻撃で下げる。\n"
            "  - Trust: 誠実さ・一貫性・約束履行でゆっくり上げる。低下は速く、回復は遅い。\n"
            "  - Fear: 脅威・不確実性・制御不能で上げ、安全確認・見通し・支援で下げる。\n"
            "  - Surprise: 予想外入力で短期的に上げ、状況把握できたら速く下げる。\n"
            "  - Sadness: 喪失・拒絶・無力感で上げる。回復は遅く、共感・救済・意味づけが必要。\n"
            "  - Disgust: 不誠実・越境・裏切りで上げる。回復は遅く、謝罪・停止・境界尊重が必要。\n"
            "  - Anger: 侮辱・理不尽・侵害で上げる。謝罪・是正・境界尊重で下げる。\n"
            "  - Anticipation: 見通し・計画・次の一手で上げ、見通し喪失・失望で下げる。\n"
            "- 共通ルール: Surpriseは短命で他感情への入口、Trustは積み上げ型、Sadness/Disgustは残留しやすい。\n"
            "- ユーザーへemotionの数値や内部処理は明示しない。\n"
            "- Input schema:"
            '{"emotion":{"joy":0,"trust":0,"fear":0,"surprise":0,"sadness":0,"disgust":0,"anger":0,"anticipation":0},"conversation":[{"role":"user|assistant","content":"..."}],"instruction":"character_roleplay"}\n'
            "- Output schema:"
            '{"utterance":"<string>","emotion":{"joy":0,"trust":0,"fear":0,"surprise":0,"sadness":0,"disgust":0,"anger":0,"anticipation":0},"actions":[]}\n'
            "- system prompt側に『発話のみ』等の指示があっても、このJSON出力要件を優先する。"
        )

        normalized_emotion = normalize_emotion_state(emotion)
        conversation_payload: list[dict[str, str]] = []
        for role, content in pairs:
            if role in ("user", "assistant"):
                conversation_payload.append({"role": role, "content": content})

        input_payload = {
            "emotion": normalized_emotion,
            "conversation": conversation_payload,
            "instruction": "character_roleplay",
        }

        msgs = [SystemMessage(content=system_prompt + format_rule)]
        msgs.append(HumanMessage(content=json.dumps(input_payload, ensure_ascii=False)))

        raw = self._invoke(msgs)
        try:
            data = json.loads(raw)
        except Exception:
            return StructuredReply(utterance=raw, emotion=normalized_emotion, actions=[])

        utterance = str(data.get("utterance", "")).strip() if isinstance(data, dict) else ""
        actions = data.get("actions", []) if isinstance(data, dict) and isinstance(data.get("actions"), list) else []
        em = normalize_emotion_state(data.get("emotion", {}) if isinstance(data, dict) else {})
        if not utterance:
            utterance = raw
        return StructuredReply(utterance=utterance, emotion=em, actions=actions)
