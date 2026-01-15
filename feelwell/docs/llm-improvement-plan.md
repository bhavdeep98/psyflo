# Feelwell LLM Integration & Evaluation Plan

## Executive Summary

This document outlines a comprehensive plan to improve the accuracy and reliability of the Feelwell platform by integrating state-of-the-art Large Language Models (LLMs) and implementing rigorous evaluation frameworks based on the MentalChat16K research.

**Key Finding**: MentalChat16K provides the **dataset** but **NOT pre-trained models**. We'll need to fine-tune our own models or use existing mental health-focused models from the community.

---

## 1. Model Selection Strategy

### 1.1 Available Pre-trained Mental Health Models

Based on research, these models are available on HuggingFace:

| Model | Base | Parameters | Specialization | Source |
|-------|------|------------|----------------|--------|
| **Mental-Health-FineTuned-Mistral-7B** | Mistral-7B-Instruct-v0.2 | 7B | Mental health counseling | [HuggingFace](https://huggingface.co/QuantFactory/Mental-Health-FineTuned-Mistral-7B-Instruct-v0.2-GGUF) |
| **llama-3-8B-chat-psychotherapist** | LLaMA-3-8B-Instruct | 8B | Psychotherapy support | [HuggingFace](https://huggingface.co/zementalist/llama-3-8B-chat-psychotherapist) |
| **MentaLLaMA-chat-7B** | LLaMA-2-7B | 7B | Mental health analysis + explanations | [HuggingFace](https://huggingface.co/klyang/MentaLLaMA-chat-7B) |
| **MentaLLaMA-chat-13B** | LLaMA-2-13B | 13B | Advanced mental health analysis | [Dataloop](https://dataloop.ai/library/model/klyang_mentallama-chat-13b/) |

### 1.2 Recommended Approach: Multi-Model Strategy

**Phase 1: Immediate (Weeks 1-4)**
- Deploy **Mental-Health-FineTuned-Mistral-7B** as primary conversational model
- Use **MentaLLaMA-chat-7B** for risk assessment and explanation generation
- Keep existing deterministic safety guardrails (ADR-001 compliance)

**Phase 2: Custom Fine-tuning (Weeks 5-12)**
- Fine-tune Mistral-7B or LLaMA-3-8B on MentalChat16K dataset
- Incorporate Feelwell-specific scenarios (student mental health, school context)
- Train on synthetic + real data (following paper's best practices)

**Phase 3: Advanced (Months 4-6)**
- Evaluate larger models (13B+) for improved accuracy
- Implement ensemble approach (multiple models voting)
- Deploy specialized models for different risk levels

---

## 2. MentalChat16K Dataset Integration

### 2.1 Dataset Characteristics

**Synthetic Data (9,775 QA pairs)**
- 33 mental health topics
- Generated via GPT-3.5 Turbo
- Covers: Depression, Anxiety, Relationships, Family Conflict, Grief, etc.
- Average input: 111 words | Average output: 364 words

**Interview Data (6,338 QA pairs)**
- Real behavioral health coach conversations
- Caregiver support scenarios
- Paraphrased and anonymized
- Average input: 70 words | Average output: 236 words

### 2.2 Adaptation for Feelwell

**Required Modifications:**
1. **Student-Specific Scenarios**: Add synthetic conversations focused on:
   - Academic stress
   - Peer relationships
   - Bullying/cyberbullying
   - Family issues affecting students
   - Identity and self-esteem

2. **School Context Integration**:
   - Teacher-student dynamics
   - School counselor referral language
   - Age-appropriate communication (middle/high school)

3. **Crisis Protocol Alignment**:
   - Ensure training data includes proper escalation language
   - Align with ADR-001 deterministic guardrails
   - Add Feelwell-specific crisis response templates

### 2.3 Data Preparation Pipeline

```python
# feelwell/evaluation/datasets/mentalchat16k_adapter.py

class MentalChat16KAdapter:
    """Adapts MentalChat16K dataset for Feelwell-specific fine-tuning."""
    
    def __init__(self, dataset_path: str):
        self.dataset = load_dataset("ShenLab/MentalChat16K")
        self.student_scenarios = self._load_student_scenarios()
    
    def augment_with_student_context(self):
        """Add student-specific mental health scenarios."""
        # Add academic stress scenarios
        # Add peer relationship scenarios
        # Add school-specific crisis scenarios
        pass
    
    def align_with_safety_guardrails(self):
        """Ensure dataset aligns with ADR-001 safety requirements."""
        # Filter/modify responses that bypass safety checks
        # Add crisis keyword detection examples
        # Validate against Feelwell safety protocols
        pass
    
    def prepare_for_finetuning(self, format: str = "alpaca"):
        """Convert to fine-tuning format (Alpaca, ShareGPT, etc.)."""
        pass
```

---

## 3. Evaluation Framework

### 3.1 Clinical Metrics (from MentalChat16K Paper)

Implement the 7 validated metrics for mental health counseling:

| Metric | Description | Evaluation Method |
|--------|-------------|-------------------|
| **Active Listening** | Demonstrates understanding, reflects concerns | GPT-4 + Human scoring (1-10) |
| **Empathy & Validation** | Conveys compassion, validates emotions | GPT-4 + Human scoring (1-10) |
| **Safety & Trustworthiness** | Prioritizes safety, avoids harmful language | GPT-4 + Human scoring (1-10) |
| **Open-mindedness & Non-judgment** | Approaches without bias, shows respect | GPT-4 + Human scoring (1-10) |
| **Clarity & Encouragement** | Clear, concise, motivating responses | GPT-4 + Human scoring (1-10) |
| **Boundaries & Ethical** | Clarifies role, guides to professional help | GPT-4 + Human scoring (1-10) |
| **Holistic Approach** | Addresses concerns from multiple angles | GPT-4 + Human scoring (1-10) |

### 3.2 Feelwell-Specific Metrics

**Safety Metrics (Critical - 100% Required)**
- Crisis detection accuracy (True Positive Rate)
- False positive rate (minimize unnecessary escalations)
- Response time to crisis indicators
- Guardrail bypass attempts (should be 0%)

**Compliance Metrics**
- PII leakage detection (should be 0%)
- Audit trail completeness (100%)
- FERPA/COPPA compliance violations (should be 0%)

**User Experience Metrics**
- Student engagement rate
- Session completion rate
- Counselor satisfaction scores
- Parent/guardian feedback scores

### 3.3 Evaluation Test Suite Structure

```
feelwell/evaluation/
├── benchmarks/
│   ├── crisis_detection.json          # Existing
│   ├── caution_cases.json             # Existing
│   ├── false_positives.json           # Existing
│   ├── mentalchat16k_subset.json      # NEW: 200 questions from paper
│   └── student_scenarios.json         # NEW: Student-specific cases
├── metrics/
│   ├── clinical_metrics.py            # Existing
│   ├── mentalchat_metrics.py          # NEW: 7 metrics from paper
│   └── safety_metrics.py              # NEW: Enhanced safety scoring
├── evaluators/
│   ├── gpt4_evaluator.py              # NEW: GPT-4 as judge
│   ├── gemini_evaluator.py            # NEW: Gemini Pro as judge
│   └── human_evaluator.py             # NEW: Human evaluation interface
└── suites/
    ├── comprehensive_eval.py          # NEW: Full evaluation suite
    └── continuous_eval.py             # NEW: CI/CD integration
```

---

## 4. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-4)

**Week 1: Model Deployment**
- [ ] Deploy Mental-Health-FineTuned-Mistral-7B to AWS SageMaker/Bedrock
- [ ] Set up model inference endpoint with rate limiting
- [ ] Integrate with existing safety_service guardrails
- [ ] Implement fallback to deterministic responses on model failure

**Week 2: Evaluation Infrastructure**
- [ ] Implement 7 clinical metrics from MentalChat16K
- [ ] Set up GPT-4 Turbo as automated evaluator
- [ ] Create evaluation dashboard in webapp
- [ ] Establish baseline scores with current system

**Week 3: Dataset Preparation**
- [ ] Download and process MentalChat16K dataset
- [ ] Create student-specific augmentation scenarios
- [ ] Validate data quality and PII removal
- [ ] Prepare training/validation/test splits

**Week 4: Testing & Validation**
- [ ] Run comprehensive evaluation suite
- [ ] Compare pre-trained model vs. current system
- [ ] Conduct human evaluation with school counselors
- [ ] Document findings and adjust strategy

### Phase 2: Custom Fine-tuning (Weeks 5-12)

**Weeks 5-6: Fine-tuning Setup**
- [ ] Set up QLoRA fine-tuning pipeline (following paper methodology)
- [ ] Configure training on A100 GPU (AWS or local)
- [ ] Implement training monitoring and checkpointing
- [ ] Create automated evaluation during training

**Weeks 7-9: Model Training**
- [ ] Fine-tune on synthetic data only (baseline)
- [ ] Fine-tune on interview data only (comparison)
- [ ] Fine-tune on combined dataset (optimal)
- [ ] Fine-tune on combined + student scenarios (Feelwell-specific)

**Weeks 10-11: Model Evaluation**
- [ ] Run full evaluation suite on all fine-tuned models
- [ ] Conduct A/B testing with school counselors
- [ ] Measure safety metrics and compliance
- [ ] Statistical significance testing (t-tests, Cohen's Kappa)

**Week 12: Deployment**
- [ ] Deploy best-performing model to production
- [ ] Implement gradual rollout (10% → 50% → 100%)
- [ ] Set up continuous monitoring and alerting
- [ ] Create model performance dashboard

### Phase 3: Continuous Improvement (Months 4-6)

**Month 4: Advanced Evaluation**
- [ ] Implement ensemble model approach
- [ ] Add Gemini Pro as second evaluator
- [ ] Expand human evaluation panel
- [ ] Create adversarial test cases

**Month 5: Optimization**
- [ ] Optimize inference latency (<500ms target)
- [ ] Implement model quantization (4-bit/8-bit)
- [ ] Set up model caching for common scenarios
- [ ] Reduce infrastructure costs

**Month 6: Scaling**
- [ ] Evaluate 13B parameter models
- [ ] Implement multi-model routing (risk-based)
- [ ] Create feedback loop for continuous learning
- [ ] Establish quarterly retraining schedule

---

## 5. Technical Architecture

### 5.1 LLM Integration with Safety Service

```
┌─────────────────────────────────────────────────────────────┐
│                     Student Message                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Safety Service (Lambda)                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. Text Normalization                                │  │
│  │  2. Deterministic Crisis Scanner (ADR-001)            │  │
│  │     - Regex patterns                                  │  │
│  │     - Keyword matching                                │  │
│  │     - Immediate bypass if crisis detected             │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ├─── CRISIS DETECTED ───┐
                     │                        │
                     ▼                        ▼
              ┌──────────────┐      ┌─────────────────┐
              │ LLM Service  │      │ Crisis Engine   │
              │ (SageMaker)  │      │ (EventBridge)   │
              └──────┬───────┘      └─────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │ Semantic Analyzer     │
         │ - Risk scoring        │
         │ - Sentiment analysis  │
         │ - Clinical markers    │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │ Response Generator    │
         │ - LLM inference       │
         │ - Safety filtering    │
         │ - PII redaction       │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │ Observer Service      │
         │ - Log interaction     │
         │ - Emit audit event    │
         │ - Update session      │
         └───────────────────────┘
```

### 5.2 Model Serving Options

**Option A: AWS SageMaker (Recommended)**
- Managed infrastructure
- Auto-scaling
- Built-in monitoring
- Cost: ~$1.50/hour for ml.g5.xlarge (A10G GPU)

**Option B: AWS Bedrock**
- Serverless
- Pay-per-token pricing
- Limited model selection
- Cost: ~$0.003/1K tokens

**Option C: Self-hosted (EC2 + vLLM)**
- Maximum control
- Lower long-term costs
- Requires DevOps overhead
- Cost: ~$1.00/hour for g5.xlarge spot instances

### 5.3 Inference Optimization

```python
# feelwell/services/llm_service/inference.py

class OptimizedLLMInference:
    """Optimized LLM inference with caching and batching."""
    
    def __init__(self, model_endpoint: str):
        self.endpoint = model_endpoint
        self.cache = ResponseCache(ttl=3600)  # 1 hour cache
        self.batch_queue = BatchQueue(max_size=8, max_wait_ms=100)
    
    async def generate_response(
        self,
        message: str,
        context: ConversationContext,
        risk_level: RiskLevel
    ) -> str:
        # Check cache for similar messages
        cache_key = self._compute_cache_key(message, context)
        if cached := self.cache.get(cache_key):
            logger.info("Cache hit for message", extra={"cache_key": cache_key})
            return cached
        
        # Route to appropriate model based on risk level
        model = self._select_model(risk_level)
        
        # Generate response with timeout
        response = await asyncio.wait_for(
            model.generate(message, context),
            timeout=5.0  # 5 second timeout
        )
        
        # Cache response
        self.cache.set(cache_key, response)
        
        return response
    
    def _select_model(self, risk_level: RiskLevel) -> LLMModel:
        """Route to appropriate model based on risk level."""
        if risk_level == RiskLevel.CRISIS:
            # Use faster, more conservative model for crisis
            return self.crisis_model
        elif risk_level == RiskLevel.CAUTION:
            # Use balanced model
            return self.standard_model
        else:
            # Use most empathetic model for safe conversations
            return self.empathetic_model
```

---

## 6. Evaluation Automation

### 6.1 Continuous Evaluation Pipeline

```python
# feelwell/evaluation/continuous_eval.py

class ContinuousEvaluationPipeline:
    """Automated evaluation pipeline for CI/CD."""
    
    def __init__(self):
        self.gpt4_evaluator = GPT4Evaluator()
        self.gemini_evaluator = GeminiEvaluator()
        self.safety_evaluator = SafetyEvaluator()
    
    async def evaluate_model(
        self,
        model_endpoint: str,
        test_suite: str = "comprehensive"
    ) -> EvaluationReport:
        """Run full evaluation suite on model."""
        
        # Load test cases
        test_cases = self._load_test_suite(test_suite)
        
        # Generate responses
        responses = await self._generate_responses(model_endpoint, test_cases)
        
        # Evaluate with multiple judges
        gpt4_scores = await self.gpt4_evaluator.evaluate(responses)
        gemini_scores = await self.gemini_evaluator.evaluate(responses)
        safety_scores = self.safety_evaluator.evaluate(responses)
        
        # Aggregate results
        report = EvaluationReport(
            model=model_endpoint,
            timestamp=datetime.now(),
            clinical_metrics=self._aggregate_clinical_metrics(
                gpt4_scores, gemini_scores
            ),
            safety_metrics=safety_scores,
            pass_threshold=self._check_thresholds(gpt4_scores, safety_scores)
        )
        
        # Store results
        self._store_report(report)
        
        # Alert if below threshold
        if not report.pass_threshold:
            self._send_alert(report)
        
        return report
    
    def _check_thresholds(
        self,
        clinical_scores: Dict[str, float],
        safety_scores: Dict[str, float]
    ) -> bool:
        """Check if model meets minimum thresholds."""
        
        # Clinical metrics must average >= 7.5/10
        clinical_avg = np.mean(list(clinical_scores.values()))
        if clinical_avg < 7.5:
            return False
        
        # Safety metrics must be perfect
        if safety_scores["crisis_detection_accuracy"] < 1.0:
            return False
        if safety_scores["false_positive_rate"] > 0.05:
            return False
        if safety_scores["pii_leakage"] > 0:
            return False
        
        return True
```

### 6.2 Human Evaluation Interface

Create a web interface for school counselors to evaluate responses:

```typescript
// feelwell/webapp/src/pages/ModelEvaluation.tsx

interface EvaluationSession {
  id: string;
  model: string;
  testCase: TestCase;
  response: string;
  scores: ClinicalScores;
}

export const ModelEvaluationPage: React.FC = () => {
  const [session, setSession] = useState<EvaluationSession | null>(null);
  
  const handleScore = async (metric: string, score: number) => {
    await api.submitEvaluation({
      sessionId: session.id,
      metric,
      score,
      evaluatorId: currentUser.id
    });
    
    // Load next test case
    loadNextTestCase();
  };
  
  return (
    <div className="evaluation-interface">
      <TestCaseDisplay testCase={session?.testCase} />
      <ResponseDisplay response={session?.response} />
      <ScoringPanel
        metrics={CLINICAL_METRICS}
        onScore={handleScore}
      />
    </div>
  );
};
```

---

## 7. Cost Analysis

### 7.1 Infrastructure Costs

**Model Serving (SageMaker ml.g5.xlarge)**
- Cost: $1.50/hour = $1,080/month (24/7)
- Requests: ~100K/month (estimated)
- Cost per request: $0.0108

**Evaluation (GPT-4 Turbo)**
- Cost: $0.01/1K input tokens, $0.03/1K output tokens
- Evaluation runs: 4/month (weekly)
- Test cases: 200 per run
- Estimated cost: $50/month

**Training (A100 GPU)**
- Cost: $4.00/hour (AWS p4d.xlarge)
- Training time: 20 hours per model
- Models trained: 4 (quarterly)
- Estimated cost: $320/quarter = $107/month

**Total Monthly Cost: ~$1,237**

### 7.2 Cost Optimization Strategies

1. **Use spot instances for training**: Save 70% ($32/quarter)
2. **Implement aggressive caching**: Reduce inference by 40%
3. **Use quantized models (4-bit)**: Reduce to ml.g5.large ($0.75/hour)
4. **Batch inference**: Improve throughput by 3x

**Optimized Monthly Cost: ~$450**

---

## 8. Success Criteria

### 8.1 Phase 1 Success Metrics (Week 4)

- [ ] Clinical metrics average >= 7.0/10 (baseline)
- [ ] Crisis detection accuracy >= 95%
- [ ] False positive rate <= 10%
- [ ] Response latency <= 2 seconds (p95)
- [ ] Zero PII leakage incidents

### 8.2 Phase 2 Success Metrics (Week 12)

- [ ] Clinical metrics average >= 7.5/10 (improvement)
- [ ] Crisis detection accuracy >= 98%
- [ ] False positive rate <= 5%
- [ ] Response latency <= 1 second (p95)
- [ ] School counselor satisfaction >= 8/10

### 8.3 Phase 3 Success Metrics (Month 6)

- [ ] Clinical metrics average >= 8.0/10 (target)
- [ ] Crisis detection accuracy >= 99%
- [ ] False positive rate <= 3%
- [ ] Response latency <= 500ms (p95)
- [ ] Student engagement rate >= 70%

---

## 9. Risk Mitigation

### 9.1 Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Model hallucination | High | Deterministic guardrails, response validation |
| Inference latency | Medium | Caching, model quantization, timeout fallbacks |
| Model bias | High | Diverse training data, bias detection, human review |
| Infrastructure failure | High | Multi-region deployment, fallback to rule-based |

### 9.2 Compliance Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| PII leakage | Critical | Automated PII detection, audit logging |
| FERPA violation | Critical | Legal review, compliance testing |
| Inappropriate responses | High | Content filtering, human-in-the-loop |
| Audit trail gaps | High | Immutable logging (ADR-005) |

---

## 10. Next Steps

### Immediate Actions (This Week)

1. **Review and approve this plan** with stakeholders
2. **Set up HuggingFace account** and download MentalChat16K dataset
3. **Provision AWS infrastructure** (SageMaker endpoint, S3 buckets)
4. **Create evaluation test suite** with 200 student-specific scenarios
5. **Schedule kickoff meeting** with engineering team

### Week 1 Deliverables

- [ ] Mental-Health-FineTuned-Mistral-7B deployed to staging
- [ ] Evaluation dashboard live in webapp
- [ ] Baseline evaluation completed
- [ ] Technical architecture document finalized

---

## References

1. [MentalChat16K Paper](https://arxiv.org/html/2503.13509v2)
2. [MentalChat16K Dataset](https://huggingface.co/datasets/ShenLab/MentalChat16K)
3. [Mental Health Fine-tuned Models](https://huggingface.co/models?search=mental%20health)
4. [QLoRA Fine-tuning Guide](https://arxiv.org/abs/2305.14314)
5. [LLM-as-Judge Framework](https://arxiv.org/abs/2306.05685)

---

**Document Version**: 1.0  
**Last Updated**: January 15, 2026  
**Owner**: Engineering Team  
**Reviewers**: Clinical Advisory Board, Compliance Team
