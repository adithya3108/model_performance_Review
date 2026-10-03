**What was wrong with the original measurement**

1. **Exact string match.** 71 of model-b's 150 responses are correct numbers in a different format (`2,779`, `**2779**`, `The answer is 2,779.`), and `score.py` marked them all wrong. model-a always answers with a bare number.
2. **Wrong answer key.** I recomputed every answer from the question text. Three keys are wrong: q006 (key says 4100, correct is 1400), q026 (10480, correct 10481) and q038 (397, correct 398).
3. **Duplicates.** Six questions appear twice. I kept the lower ID and dropped q031, q039, q042, q044, q047 and q049, leaving 50 questions.
4. **Unequal settings.** model-a ran at temperature 0.0 and model-b at 0.7. I cannot correct for this.

**Numbers** (`python analyse.py`)

| Step | model-a | model-b |
|---|---|---|
| Original | 69.6% | 39.3% |
| Correct key | 75.0% | 41.7% |
| Plus last number in the response | 75.0% | 77.4% |
| Plus duplicates removed (**final**) | **72.0%** | **80.0%** |

**Is model-a better?** No. On this data model-b is 8 points ahead, but I am not confident in that gap. The 95% bootstrap interval (resampling questions) is −21.3 to +4.7 points, and a paired permutation test gives p ≈ 0.27. The gap comes almost entirely from multiplication (54.5% vs 71.2%).

**What these numbers do not prove**

- That either model is better in general. The test is 50 short arithmetic questions.
- How the models compare at the same temperature.
- How much the answers vary between runs. At temperature 0, model-a's three runs are identical.
- Anything about following an answer format. If a bare number is required, model-b's formatting is a real failure, and the original scoring was right to penalise it.
