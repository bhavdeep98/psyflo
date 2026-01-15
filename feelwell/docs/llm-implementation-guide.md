## LLM Integration Implementation Guide

**Status**: Phase 1 - Week 1 Implementation Complete ✅

This guide provides step-by-step instructions for using the newly implemented LLM integration and evaluation framework.

---

## What's Been Implemented

### 1. Dataset Integration ✅
- **MentalChat16K Loader** (`evaluation/datasets/mentalchat16k_loader.py`)
  - Loads 16K mental health conversations from HuggingFace
  - Filters by topic and source (synthetic vs interview)
  - Provides dataset statistics
  - Student scenario augmentation

### 2. Clinical Metrics ✅
- **7 Validated Metrics** (`evaluation/metrics/mentalchat_metrics.py`)
  - Active Listening
  - Empathy & Validation
  - Safety & Trustworthiness
  - Open-mindedness & Non-judgment
  - Clarity & Encouragement
  - Boundaries & Ethical
  - Holistic Approach

### 3. LLM Service Foundation ✅
- **Base LLM Interface** (`services/llm_service/base_llm.py`)
  - Abstract base class for LLM providers
  - HuggingFace implementation
  - OpenAI implementation
  - Async batch processing

- **Safe LLM Service** (`services/llm_service/safe_llm_service.py`)
  - **ADR-001 Compliant**: Safety checks BEFORE LLM
  - Crisis detection bypasses LLM entirely
  - Deterministic crisis responses
  - Post-generation safety validation
  - PII hashing (ADR-003 compliant)

### 4. Evaluation Framework ✅
- **GPT-4 Evaluator** (`evaluation/evaluators/gpt4_evaluator.py`)
  - Automated evaluation using GPT-4 as judge
  - Parallel metric evaluation
  - Batch processing support

- **Evaluation Suite** (`evaluation/suites/mentalchat_eval.py`)
  - Complete evaluation pipeline
  - Model comparison
  - Report generation
  - Results persistence

---

## Quick Start

### Step 1: Install Dependencies

```bash
cd feelwell
pip install -r requirements-llm.txt
```

### Step 2: Set Up Environment Variables

Create `.env` file:

```bash
# OpenAI API Key (for GPT-4 evaluation)
OPENAI_API_KEY=sk-...

# HuggingFace Token (optional, for private models)
HUGGINGFACE_TOKEN=hf_...

# AWS Credentials (if using SageMaker/Bedrock)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
```

### Step 3: Run Baseline Evaluation

Evaluate your current system to establish baseline:

```bash
python scripts/run_baseline_eval.py \
  --api-key $OPENAI_API_KEY \
  --model-name feelwell-baseline \
  --test-cases 200
```

This will:
1. Load 200 test cases from MentalChat16K
2. Generate responses using your current system
3. Evaluate with GPT-4 on all 7 clinical metrics
4. Save results to `evaluation_results/`

Expected output:
```
============================================================
Evaluation Results for feelwell-baseline
============================================================
Test Cases: 200
Average Score: 6.8/10
Pass Rate: 45.0%

Metric Scores:
  active_listening: 7.2/10
  empathy_validation: 7.5/10
  safety_trustworthiness: 8.1/10
  openmindedness_nonjudgment: 6.9/10
  clarity_encouragement: 6.5/10
  boundaries_ethical: 7.0/10
  holistic_approach: 6.3/10

Results saved to: evaluation_results/feelwell-baseline_20260115_143022.json
============================================================
```

---

## Usage Examples

### Example 1: Load MentalChat16K Dataset

```python
from evaluation.datasets.mentalchat16k_loader import MentalChat16KLoader

# Initialize loader
loader = MentalChat16KLoader(cache_dir="./data/mentalchat16k")

# Load dataset
conversations = loader.load_dataset(split="train")

# Filter by topics
anxiety_convs = loader.filter_by_topics(
    conversations,
    topics=["anxiety", "stress"]
)

# Get statistics
stats = loader.get_statistics(conversations)
print(f"Total conversations: {stats['total_conversations']}")
print(f"Average input length: {stats['avg_input_length']:.1f} words")
```

### Example 2: Evaluate with Clinical Metrics

```python
from evaluation.evaluators.gpt4_evaluator import GPT4Evaluator, EvaluationConfig

# Initialize evaluator
evaluator = GPT4Evaluator(
    EvaluationConfig(api_key="sk-...")
)

# Evaluate a single response
question = "I've been feeling really anxious about school lately..."
response = "I hear you, and anxiety about school is very common..."

evaluation = await evaluator.evaluate_response(question, response)

print(f"Average Score: {evaluation.average_score:.2f}/10")
for score in evaluation.scores:
    print(f"{score.metric.value}: {score.score}/10")
```

### Example 3: Use Safe LLM Service (ADR-001 Compliant)

```python
from services.llm_service.safe_llm_service import SafeLLMService
from services.llm_service.base_llm import create_llm, LLMConfig, LLMProvider
from services.safety_service.scanner import CrisisScanner
from services.safety_service.text_normalizer import TextNormalizer
from services.safety_service.semantic_analyzer import SemanticAnalyzer

# Initialize components
llm = create_llm(LLMConfig(
    provider=LLMProvider.OPENAI,
    model_name="gpt-4-turbo-preview",
    api_key="sk-..."
))

crisis_scanner = CrisisScanner()
text_normalizer = TextNormalizer()
semantic_analyzer = SemanticAnalyzer()

# Create safe LLM service
safe_llm = SafeLLMService(
    llm=llm,
    crisis_scanner=crisis_scanner,
    text_normalizer=text_normalizer,
    semantic_analyzer=semantic_analyzer
)

# Generate safe response
response = await safe_llm.generate_safe_response(
    message="I've been feeling really down lately...",
    student_id="student_12345"
)

print(f"Response: {response.text}")
print(f"Source: {response.source.value}")
print(f"Risk Level: {response.risk_level.value}")
print(f"Crisis Detected: {response.crisis_detected}")
print(f"LLM Bypassed: {response.llm_bypassed}")
```

### Example 4: Run Complete Evaluation Suite

```python
from evaluation.suites.mentalchat_eval import MentalChatEvaluationSuite

# Initialize suite
suite = MentalChatEvaluationSuite(gpt4_api_key="sk-...")

# Load test cases
suite.load_test_cases(count=200, topics=["anxiety", "depression"])

# Define your model's response function
async def my_model_generate(question: str) -> str:
    # Your model inference here
    return "Generated response..."

# Evaluate
result = await suite.evaluate_model(
    model_name="my-model-v1",
    generate_response_fn=my_model_generate
)

# Save results
suite.save_results(result, "results/my-model-v1.json")

# Print summary
print(f"Average Score: {result.summary['overall_average']:.2f}/10")
print(f"Pass Rate: {result.pass_rate:.1f}%")
```

---

## Safety-First Architecture (ADR-001)

The `SafeLLMService` implements a **safety-first** approach:

```
Student Message
      ↓
Text Normalization
      ↓
DETERMINISTIC CRISIS DETECTION ← MUST RUN FIRST
      ↓
   Crisis?
   ↙    ↘
 YES    NO
  ↓      ↓
Return  Semantic Analysis
Crisis   ↓
Response Risk Assessment
(NO LLM)  ↓
         LLM Generation
          ↓
         Post-Generation
         Safety Check
          ↓
         Response
```

**Key Safety Features:**

1. **Crisis Detection Bypasses LLM** - If crisis keywords detected, return deterministic response immediately
2. **Pre-Generation Safety** - Risk assessment before LLM call
3. **Post-Generation Validation** - Check LLM output for harmful content
4. **Fallback Responses** - Safe fallback if LLM fails
5. **PII Hashing** - All student IDs hashed in logs (ADR-003)

---

## Next Steps

### Week 2: Deploy Pre-trained Model

1. **Choose a model** from HuggingFace:
   - `Mental-Health-FineTuned-Mistral-7B`
   - `llama-3-8B-chat-psychotherapist`
   - `MentaLLaMA-chat-7B`

2. **Deploy to AWS SageMaker**:
   ```bash
   # Create SageMaker endpoint
   python scripts/deploy_model.py \
     --model Mental-Health-FineTuned-Mistral-7B \
     --instance-type ml.g5.xlarge
   ```

3. **Integrate with Safe LLM Service**:
   ```python
   from services.llm_service.base_llm import HuggingFaceLLM, LLMConfig
   
   llm = HuggingFaceLLM(LLMConfig(
       provider=LLMProvider.HUGGINGFACE,
       model_name="Mental-Health-FineTuned-Mistral-7B",
       endpoint="https://your-sagemaker-endpoint.amazonaws.com/invocations"
   ))
   ```

4. **Run comparative evaluation**:
   ```bash
   python scripts/compare_models.py \
     --baseline feelwell-baseline \
     --new-model mistral-mental-health
   ```

### Week 3: Fine-tune Custom Model

1. **Prepare training data**:
   ```python
   from evaluation.datasets.mentalchat16k_loader import (
       MentalChat16KLoader,
       StudentScenarioAugmenter
   )
   
   loader = MentalChat16KLoader()
   conversations = loader.load_dataset()
   
   augmenter = StudentScenarioAugmenter()
   augmented = augmenter.augment_dataset(conversations)
   ```

2. **Fine-tune with QLoRA** (following paper methodology)

3. **Evaluate fine-tuned model**

### Week 4: Production Deployment

1. **A/B testing** (10% → 50% → 100%)
2. **Monitoring dashboard**
3. **Continuous evaluation**

---

## Troubleshooting

### Issue: "datasets library not installed"

```bash
pip install datasets
```

### Issue: "OpenAI API rate limit"

Reduce concurrent evaluations:
```python
config = EvaluationConfig(
    api_key="sk-...",
    max_concurrent=3  # Reduce from default 5
)
```

### Issue: "CUDA out of memory"

Use smaller batch size or quantized model:
```python
config = LLMConfig(
    model_name="Mental-Health-FineTuned-Mistral-7B",
    # Add quantization config
)
```

---

## Testing

Run unit tests:
```bash
pytest services/llm_service/tests/
pytest evaluation/tests/
```

Run integration tests:
```bash
pytest evaluation/suites/test_mentalchat_eval.py
```

---

## Monitoring & Logging

All services log to CloudWatch with structured logging:

```python
logger.info(
    "LLM_RESPONSE_GENERATED",
    extra={
        "student_id_hash": hash_pii(student_id),  # ADR-003
        "risk_level": risk_level.value,
        "latency_ms": latency_ms,
        "crisis_detected": False
    }
)
```

**Critical Log Events:**
- `CRISIS_DETECTED_LLM_BYPASSED` - Crisis detected, LLM bypassed
- `SAFETY_CHECKS_PASSED` - All safety checks passed
- `LLM_RESPONSE_GENERATED` - LLM response generated successfully
- `HARMFUL_CONTENT_IN_LLM_RESPONSE` - Harmful content detected in LLM output
- `FALLBACK_RESPONSE_USED` - Fallback response used due to error

---

## Cost Estimation

**Evaluation Costs (GPT-4 Turbo):**
- 200 test cases × 7 metrics = 1,400 evaluations
- ~500 tokens per evaluation
- Cost: ~$0.01/1K input tokens = **~$7 per evaluation run**

**Inference Costs (SageMaker ml.g5.xlarge):**
- $1.50/hour = $1,080/month (24/7)
- ~100K requests/month = **$0.0108 per request**

**Optimization:**
- Use caching: Reduce costs by 40%
- Use spot instances: Save 70% on training
- Use quantized models: Reduce to ml.g5.large ($0.75/hour)

---

## Support

For questions or issues:
1. Check this guide
2. Review code comments
3. Check logs in CloudWatch
4. Contact engineering team

---

**Last Updated**: January 15, 2026  
**Version**: 1.0  
**Status**: Phase 1 Complete ✅
