# Code Completions — Choice-Grounded Dimension Discovery

**Choice context:** A developer is evaluating which code implementation to use for a software project, considering factors like security, correctness, readability, and best practices.

## Parameters

- Pairs sampled: 150
- Reasons per side: 5
- Total raw reasons: 1500
- Dedup method: llm
- Themes/clusters: 60
- Dimensions requested: 25
- Dimensions produced: 25
- Seed: 42
- Model: Qwen/Qwen3-32B

## Dimensions

**1. Code Simplicity**: Complex ↔ Simple
   Subsumed reasons: [1, 2, 33, 42]

**2. Modularity**: Monolithic ↔ Modular
   Subsumed reasons: [7, 12, 17, 13, 37]

**3. Functionality Clarity**: Ambiguous ↔ Clear
   Subsumed reasons: [3, 16, 42, 50]

**4. System-Level Control**: High-level ↔ Low-level
   Subsumed reasons: [4, 18, 28, 57]

**5. Automation Focus**: Manual ↔ Automated
   Subsumed reasons: [6, 14, 30, 48]

**6. Web Integration**: Standalone ↔ Web-focused
   Subsumed reasons: [8, 19, 23, 24]

**7. Security Focus**: Unsecured ↔ Secure
   Subsumed reasons: [9, 21, 31, 55]

**8. Error Handling**: Unreliable ↔ Robust
   Subsumed reasons: [15, 22, 44, 55]

**9. Testability**: Untestable ↔ Testable
   Subsumed reasons: [22, 44, 49]

**10. User Interaction**: Passive ↔ Interactive
   Subsumed reasons: [25, 32, 39, 46]

**11. Data Processing**: Minimal ↔ Data-rich
   Subsumed reasons: [20, 40, 42, 52]

**12. Dependency Use**: No dependencies ↔ Heavy dependencies
   Subsumed reasons: [10, 35, 41, 53]

**13. Immediate Results**: Delayed ↔ Immediate
   Subsumed reasons: [5, 16, 32, 53]

**14. Educational Value**: Practical only ↔ Educational
   Subsumed reasons: [60]

**15. RESTful Design**: Non-REST ↔ RESTful
   Subsumed reasons: [23, 29]

**16. Database Integration**: No database ↔ Database-focused
   Subsumed reasons: [27, 34, 38]

**17. File System Interaction**: No file access ↔ File-focused
   Subsumed reasons: [11, 28]

**18. Command-Line Focus**: GUI-based ↔ CLI-focused
   Subsumed reasons: [28]

**19. Real-Time Interaction**: Batch ↔ Real-time
   Subsumed reasons: [46]

**20. Scalability**: Limited ↔ Scalable
   Subsumed reasons: [49]

**21. Convention-Driven**: Ad-hoc ↔ Conventional
   Subsumed reasons: [36]

**22. Declarative Style**: Imperative ↔ Declarative
   Subsumed reasons: [44, 45]

**23. Object-Oriented Design**: Procedural ↔ Object-oriented
   Subsumed reasons: [47]

**24. Integration Readiness**: Isolated ↔ Integrated
   Subsumed reasons: [26, 58]

**25. User Experience**: Basic ↔ Polished
   Subsumed reasons: [33, 43]

## Coverage

- Coverage rate: 99.9%
- Orphan reasons: 1
