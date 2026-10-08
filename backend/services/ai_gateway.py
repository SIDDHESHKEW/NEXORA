"""Central AI Gateway managing multi-provider routing, timeouts, repair retries, validation, fallbacks, and audit logging."""

import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Set
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.events import event_bus
from backend.models.governance import AIInteraction
from backend.services.ai_schemas import (
    AILessonOutput,
    AIRecapOutput,
    AIPracticeQuestionsOutput,
    AITutorOutput,
    AIReteachOutput,
    AIAcademicOutput,
)
from backend.services.ai_validators import (
    AIValidationError,
    validate_lesson_structure,
    validate_recap_structure,
    validate_practice_questions,
    validate_tutor_response,
    validate_reteach_segment,
    validate_academic_facts,
)
from backend.services.providers.base import BaseAIProvider
from backend.services.providers.gemini import GeminiProvider
from backend.services.providers.grok import GrokProvider

logger = logging.getLogger("sgsu.ai.gateway")

FALLBACKS_DIR = os.path.join(os.path.dirname(__file__), "ai_fallbacks")


class AIGateway:
    def __init__(self):
        self.gemini_provider = GeminiProvider()
        self.grok_provider = GrokProvider()

    def _load_fallback_json(self, filename: str) -> Any:
        path = os.path.join(FALLBACKS_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _log_interaction(
        self,
        db: Optional[Session],
        function_name: str,
        provider: str,
        model: str,
        status: str,
        latency_ms: int,
        validation_passed: bool,
        fallback_reason: Optional[str] = None,
        context_ref: Optional[str] = None,
        user_id: Optional[int] = None,
        role: Optional[str] = None,
    ) -> None:
        """Record AI call into ai_interactions table and emit event."""
        if db is not None:
            try:
                interaction = AIInteraction(
                    function=function_name,
                    model=model,
                    provider=provider,
                    status=status,
                    latency_ms=latency_ms,
                    validation_passed=validation_passed,
                    fallback_reason=fallback_reason,
                    context_ref=context_ref,
                    user_id=user_id,
                    role=role,
                )
                db.add(interaction)
                db.commit()
            except Exception as e:
                logger.error(f"Failed to log AI interaction: {e}")
                db.rollback()

        # Emit in-process event
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                event_bus.emit(
                    "ai.call_completed",
                    function=function_name,
                    status=status,
                    provider=provider,
                    latency_ms=latency_ms,
                )
            )
        except RuntimeError:
            pass

    async def _execute_with_routing(
        self,
        prompt: str,
        system_prompt: str,
        parse_model_cls: Any,
        validator_func: Any,
        validator_args: tuple,
        timeout_s: float = 25.0,
    ) -> tuple[Any, str, str]:
        """Try Gemini, then Grok, with repair retry, returning (parsed_obj, provider_name, model_name)."""
        providers: List[BaseAIProvider] = []
        if self.gemini_provider.has_keys():
            providers.append(self.gemini_provider)
        if self.grok_provider.has_keys():
            providers.append(self.grok_provider)

        if not providers:
            raise RuntimeError("NO_CONFIGURED_PROVIDERS")

        last_error = None
        for provider in providers:
            try:
                # 1. Primary call
                raw_json = await provider.generate_json(prompt, system_prompt, timeout_s=timeout_s)
                try:
                    data = json.loads(raw_json)
                    obj = parse_model_cls.model_validate(data)
                    validator_func(obj, *validator_args)
                    return obj, provider.provider_name, provider.model_name
                except Exception as parse_or_val_err:
                    logger.warning(f"Provider {provider.provider_name} returned invalid output: {parse_or_val_err}. Attempting 1 repair retry...")
                    # 2. One repair retry
                    repair_prompt = (
                        f"The following output was rejected with error: {str(parse_or_val_err)}\n\n"
                        f"OUTPUT:\n{raw_json}\n\n"
                        f"Please output strictly corrected JSON conforming to the schema and instructions without any extra text."
                    )
                    repaired_raw = await provider.generate_json(repair_prompt, system_prompt, timeout_s=timeout_s)
                    repaired_data = json.loads(repaired_raw)
                    obj = parse_model_cls.model_validate(repaired_data)
                    validator_func(obj, *validator_args)
                    return obj, provider.provider_name, provider.model_name
            except Exception as e:
                logger.warning(f"Provider {provider.provider_name} attempt failed: {e}")
                last_error = e

        raise RuntimeError(f"All AI providers failed: {last_error}")

    # --- 1. generate_lesson ---
    async def generate_lesson(
        self,
        topic: Any,
        outcomes: List[Any],
        source: Optional[Any],
        scope: str = "full",
        instruction: Optional[str] = None,
        user_id: Optional[int] = None,
        role: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> tuple[AILessonOutput, str]:
        """Generate structured lesson blocks mapped to outcomes and grounded in approved source."""
        start_time = time.time()
        outcome_ids = [getattr(o, "id", o) for o in outcomes]
        citation = getattr(source, "citation", "Goodfellow et al. Deep Learning, MIT Press, 2016.")
        is_approved = getattr(source, "approved", True) if source else False
        topic_ref = getattr(topic, "id", str(topic))

        # Policy & fallback check
        if settings.AI_FORCE_FALLBACK or not source or not is_approved:
            fallback_reason = "FORCED_FALLBACK" if settings.AI_FORCE_FALLBACK else "NO_APPROVED_SOURCE"
            fallback_data = self._load_fallback_json("lesson.json")
            obj = AILessonOutput.model_validate(fallback_data)
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_interaction(
                db, "generate_lesson", "fallback", "deterministic", "FALLBACK",
                latency_ms, True, fallback_reason, f"topic:{topic_ref}", user_id, role
            )
            return obj, "FALLBACK"

        # Live Prompt Composition
        system_prompt = (
            "You are an expert AI curriculum designer. Generate structured lesson blocks for an engineering course. "
            "You must strictly produce blocks in this exact order: "
            "TITLE, OBJECTIVES, EXPLANATION (for each LO), KEY_CONCEPTS, EXAMPLE, MISCONCEPTION, QUICK_CHECK, SOURCE. "
            f"The SOURCE citation must be exactly: '{citation}'."
        )
        prompt = (
            f"Topic: {topic.title}\n"
            f"Learning Outcomes: {[f'{o.code}: {o.statement}' for o in outcomes]}\n"
            f"Approved Source Citation: {citation}\n"
            f"Source Content Summary: {source.body_text[:1200] if source else ''}\n"
            f"Additional Instructions: {instruction or 'Standard university lecture structure'}\n"
            f"Output JSON with 'title' and 'blocks' array. Outcome IDs available: {outcome_ids}."
        )

        try:
            obj, provider, model = await self._execute_with_routing(
                prompt=prompt,
                system_prompt=system_prompt,
                parse_model_cls=AILessonOutput,
                validator_func=validate_lesson_structure,
                validator_args=(outcome_ids, citation),
                timeout_s=settings.AI_TIMEOUT_S,
            )
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_interaction(
                db, "generate_lesson", provider, model, "OK",
                latency_ms, True, None, f"topic:{topic.id}", user_id, role
            )
            return obj, "LIVE"
        except Exception as e:
            logger.warning(f"generate_lesson failed live: {e}. Falling back...")
            fallback_data = self._load_fallback_json("lesson.json")
            obj = AILessonOutput.model_validate(fallback_data)
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_interaction(
                db, "generate_lesson", "fallback", "deterministic", "FALLBACK",
                latency_ms, False, str(e)[:100], f"topic:{topic.id}", user_id, role
            )
            return obj, "FALLBACK"

    # --- 2. generate_explanation / recap ---
    async def generate_explanation(
        self,
        outcome: Any,
        misconception: Optional[Any],
        source: Optional[Any],
        user_id: Optional[int] = None,
        role: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> tuple[AIRecapOutput, str]:
        """Generate targeted concept explanation / recap addressing a specific misconception."""
        start_time = time.time()
        if settings.AI_FORCE_FALLBACK or not source:
            fallback_reason = "FORCED_FALLBACK" if settings.AI_FORCE_FALLBACK else "NO_APPROVED_SOURCE"
            fallback_data = self._load_fallback_json("recap.json")
            obj = AIRecapOutput.model_validate(fallback_data)
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_interaction(
                db, "generate_explanation", "fallback", "deterministic", "FALLBACK",
                latency_ms, True, fallback_reason, f"lo:{getattr(outcome, 'id', str(outcome))}", user_id, role
            )
            return obj, "FALLBACK"

        misc_desc = misconception.description if misconception else "general conceptual gap"
        system_prompt = "You are an AI learning assistant. Explain concepts clearly and concisely under 180 words with exactly 3 bullet points."
        prompt = (
            f"Outcome: {outcome.code} - {outcome.statement}\n"
            f"Target Misconception: {misc_desc}\n"
            f"Source material: {source.body_text[:1000] if source else ''}\n"
            f"Generate JSON with 'recap_text' (under 180 words explaining why this misconception occurs and the correct mechanism) "
            f"and 'key_points' (array of exactly 3 bullet points)."
        )

        try:
            obj, provider, model = await self._execute_with_routing(
                prompt=prompt,
                system_prompt=system_prompt,
                parse_model_cls=AIRecapOutput,
                validator_func=validate_recap_structure,
                validator_args=(),
                timeout_s=settings.AI_TIMEOUT_S,
            )
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_interaction(
                db, "generate_explanation", provider, model, "OK",
                latency_ms, True, None, f"lo:{getattr(outcome, 'id', str(outcome))}", user_id, role
            )
            return obj, "LIVE"
        except Exception as e:
            fallback_data = self._load_fallback_json("recap.json")
            obj = AIRecapOutput.model_validate(fallback_data)
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_interaction(
                db, "generate_explanation", "fallback", "deterministic", "FALLBACK",
                latency_ms, False, str(e)[:100], f"lo:{getattr(outcome, 'id', str(outcome))}", user_id, role
            )
            return obj, "FALLBACK"

    # --- 3. generate_practice_questions ---
    async def generate_practice_questions(
        self,
        outcome: Any,
        misconceptions: List[Any],
        source: Optional[Any],
        n: int = 3,
        forbidden_stems: Optional[List[str]] = None,
        user_id: Optional[int] = None,
        role: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> tuple[AIPracticeQuestionsOutput, str]:
        """Generate exactly 3 practice questions with 4 options each (1 correct)."""
        start_time = time.time()
        allowed_tags = {getattr(m, "tag", str(m)) for m in misconceptions} if misconceptions else set()

        if settings.AI_FORCE_FALLBACK or not source:
            fallback_reason = "FORCED_FALLBACK" if settings.AI_FORCE_FALLBACK else "NO_APPROVED_SOURCE"
            fallback_data = self._load_fallback_json("practice_bank.json")
            obj = AIPracticeQuestionsOutput.model_validate({"questions": fallback_data})
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_interaction(
                db, "generate_practice_questions", "fallback", "deterministic", "FALLBACK",
                latency_ms, True, fallback_reason, f"lo:{getattr(outcome, 'id', str(outcome))}", user_id, role
            )
            return obj, "FALLBACK"

        system_prompt = (
            "You are an assessment author. Generate exactly 3 multiple-choice practice questions. "
            "Each question must have exactly 4 options (A, B, C, D) with exactly one correct option. "
            "Do not duplicate exit quiz stems."
        )
        prompt = (
            f"Learning Outcome: {outcome.code} - {outcome.statement}\n"
            f"Allowed Misconception Tags: {list(allowed_tags)}\n"
            f"Source Text: {source.body_text[:1000] if source else ''}\n"
            f"Forbidden Stems: {forbidden_stems or []}\n"
            f"Output JSON with 'questions' array containing 3 questions."
        )

        try:
            obj, provider, model = await self._execute_with_routing(
                prompt=prompt,
                system_prompt=system_prompt,
                parse_model_cls=AIPracticeQuestionsOutput,
                validator_func=validate_practice_questions,
                validator_args=(outcome.id, forbidden_stems, allowed_tags),
                timeout_s=settings.AI_TIMEOUT_S,
            )
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_interaction(
                db, "generate_practice_questions", provider, model, "OK",
                latency_ms, True, None, f"lo:{getattr(outcome, 'id', str(outcome))}", user_id, role
            )
            return obj, "LIVE"
        except Exception as e:
            fallback_data = self._load_fallback_json("practice_bank.json")
            obj = AIPracticeQuestionsOutput.model_validate({"questions": fallback_data})
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_interaction(
                db, "generate_practice_questions", "fallback", "deterministic", "FALLBACK",
                latency_ms, False, str(e)[:100], f"lo:{getattr(outcome, 'id', str(outcome))}", user_id, role
            )
            return obj, "FALLBACK"

    # --- 4. generate_tutor_response ---
    async def generate_tutor_response(
        self,
        question: str,
        outcome: Optional[Any],
        source: Optional[Any],
        user_id: Optional[int] = None,
        role: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> tuple[AITutorOutput, str]:
        """Generate grounded AI tutor answer under 220 words."""
        start_time = time.time()
        # Hash + truncate student question for privacy logging
        q_hash = hashlib.sha256(question.encode("utf-8")).hexdigest()[:8]
        context_ref = f"q:{q_hash}:{question[:120]}"

        if settings.AI_FORCE_FALLBACK or not source:
            fallback_reason = "FORCED_FALLBACK" if settings.AI_FORCE_FALLBACK else "NO_APPROVED_SOURCE"
            fallback_data = self._load_fallback_json("tutor.json")
            obj = AITutorOutput.model_validate(fallback_data)
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_interaction(
                db, "generate_tutor_response", "fallback", "deterministic", "FALLBACK",
                latency_ms, True, fallback_reason, context_ref, user_id, role
            )
            return obj, "FALLBACK"

        system_prompt = (
            "You are a patient academic tutor. Answer the student's question grounded strictly in the provided course material. "
            "Never exceed 220 words. Provide clear conceptual explanations without solving graded exam questions directly."
        )
        prompt = (
            f"Approved Course Material: {source.body_text[:1200] if source else ''}\n"
            f"Topic/Outcome: {outcome.statement if outcome else 'Neural Networks'}\n"
            f"Student Question: {question}\n"
            f"Return JSON with 'answer', 'topic', 'source', 'label', and 'mode'."
        )

        try:
            obj, provider, model = await self._execute_with_routing(
                prompt=prompt,
                system_prompt=system_prompt,
                parse_model_cls=AITutorOutput,
                validator_func=validate_tutor_response,
                validator_args=(),
                timeout_s=settings.AI_TIMEOUT_S,
            )
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_interaction(
                db, "generate_tutor_response", provider, model, "OK",
                latency_ms, True, None, context_ref, user_id, role
            )
            return obj, "LIVE"
        except Exception as e:
            fallback_data = self._load_fallback_json("tutor.json")
            obj = AITutorOutput.model_validate(fallback_data)
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_interaction(
                db, "generate_tutor_response", "fallback", "deterministic", "FALLBACK",
                latency_ms, False, str(e)[:100], context_ref, user_id, role
            )
            return obj, "FALLBACK"

    # --- 5. generate_reteach_segment ---
    async def generate_reteach_segment(
        self,
        outcome: Any,
        facts: Dict[str, Any],
        source: Optional[Any],
        user_id: Optional[int] = None,
        role: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> tuple[AIReteachOutput, str]:
        """Generate a 10-minute reteach segment with outline, worked example, and 2 check items."""
        start_time = time.time()
        if settings.AI_FORCE_FALLBACK or not source:
            fallback_reason = "FORCED_FALLBACK" if settings.AI_FORCE_FALLBACK else "NO_APPROVED_SOURCE"
            fallback_data = self._load_fallback_json("reteach.json")
            obj = AIReteachOutput.model_validate(fallback_data)
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_interaction(
                db, "generate_reteach_segment", "fallback", "deterministic", "FALLBACK",
                latency_ms, True, fallback_reason, f"lo:{getattr(outcome, 'id', str(outcome))}", user_id, role
            )
            return obj, "FALLBACK"

        system_prompt = (
            "You are a teacher educator. Create a 10-minute reteach lesson segment containing: "
            "an outline totaling exactly 10 minutes, a worked example, and exactly 2 check questions with answers."
        )
        prompt = (
            f"Outcome: {outcome.code} - {outcome.statement}\n"
            f"Class Evidence Facts: {facts}\n"
            f"Course Text: {source.body_text[:1200] if source else ''}\n"
            f"Return JSON matching AIReteachOutput schema."
        )

        try:
            obj, provider, model = await self._execute_with_routing(
                prompt=prompt,
                system_prompt=system_prompt,
                parse_model_cls=AIReteachOutput,
                validator_func=validate_reteach_segment,
                validator_args=(),
                timeout_s=settings.AI_TIMEOUT_S,
            )
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_interaction(
                db, "generate_reteach_segment", provider, model, "OK",
                latency_ms, True, None, f"lo:{getattr(outcome, 'id', str(outcome))}", user_id, role
            )
            return obj, "LIVE"
        except Exception as e:
            fallback_data = self._load_fallback_json("reteach.json")
            obj = AIReteachOutput.model_validate(fallback_data)
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_interaction(
                db, "generate_reteach_segment", "fallback", "deterministic", "FALLBACK",
                latency_ms, False, str(e)[:100], f"lo:{getattr(outcome, 'id', str(outcome))}", user_id, role
            )
            return obj, "FALLBACK"

    # --- 6. generate_academic_recommendation ---
    async def generate_academic_recommendation(
        self,
        facts: Dict[str, Any],
        user_id: Optional[int] = None,
        role: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> tuple[AIAcademicOutput, str]:
        """Generate academic leadership note under 80 words containing ONLY numbers found in facts."""
        start_time = time.time()
        if settings.AI_FORCE_FALLBACK:
            fallback_data = self._load_fallback_json("academic.json")
            obj = AIAcademicOutput.model_validate(fallback_data)
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_interaction(
                db, "generate_academic_recommendation", "fallback", "deterministic", "FALLBACK",
                latency_ms, True, "FORCED_FALLBACK", "admin:academic", user_id, role
            )
            return obj, "FALLBACK"

        system_prompt = (
            "You are an academic policy advisor. Draft a concise institutional recommendation under 80 words. "
            "CRITICAL: Do NOT mention any individual students. Every number in your response MUST already exist in the provided facts."
        )
        prompt = (
            f"Validated Academic Facts: {facts}\n"
            f"Draft institutional summary text in JSON: {{ 'text': '...' }}."
        )

        try:
            obj, provider, model = await self._execute_with_routing(
                prompt=prompt,
                system_prompt=system_prompt,
                parse_model_cls=AIAcademicOutput,
                validator_func=validate_academic_facts,
                validator_args=(facts,),
                timeout_s=settings.AI_TIMEOUT_S,
            )
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_interaction(
                db, "generate_academic_recommendation", provider, model, "OK",
                latency_ms, True, None, "admin:academic", user_id, role
            )
            return obj, "LIVE"
        except Exception as e:
            fallback_data = self._load_fallback_json("academic.json")
            obj = AIAcademicOutput.model_validate(fallback_data)
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_interaction(
                db, "generate_academic_recommendation", "fallback", "deterministic", "FALLBACK",
                latency_ms, False, str(e)[:100], "admin:academic", user_id, role
            )
            return obj, "FALLBACK"


ai_gateway = AIGateway()
