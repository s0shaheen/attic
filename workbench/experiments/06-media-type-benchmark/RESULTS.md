## Per-Media-Type Cost & Time Matrix

_Generated 2026-04-03 from Exp 06 benchmark results_

| Type                         | N   | Perceive cost | Perceive time | Classify cost | Classify time | Embed cost | **Gemini total** |
| ---------------------------- | --- | ------------- | ------------- | ------------- | ------------- | ---------- | ---------------- |
| **Instagram Image**          | 13  | $0.0011       | 12.3s         | $0.00083      | 5.9s          | $0.00001   | **$0.0019**      |
| **Instagram Slideshow**      | 13  | $0.0024       | 17.8s         | $0.0016       | 8.0s          | $0.00001   | **$0.0040**      |
| **Instagram Video**          | 67  | $0.0018       | 22.6s         | $0.0014       | 8.1s          | $0.00001   | **$0.0032**      |
| _TT video (Exp 03 baseline)_ | 105 | $0.0024       | 26.8s         | $0.0019       | 8.4s          | $0.00001   | _$0.0043_        |

### Detailed Token Usage

| Type                | P1 input tok | P1 output tok | P2 input tok | P2 output tok |
| ------------------- | ------------ | ------------- | ------------ | ------------- |
| Instagram Image     | 2564         | 1192          | 4230         | 332           |
| Instagram Slideshow | 7536         | 2055          | 9309         | 342           |
| Instagram Video     | 5103         | 1710          | 7822         | 345           |
