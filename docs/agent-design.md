# Agent Design — Autonomous Engineering Intelligence Platform

## 1. Agent Philosophy

Agents in AEIP are **specialized, bounded reasoning units**. Each agent has:
- A specific domain of expertise
- A defined set of tools it can use
- A specific output format
- Clear success criteria

Agents do NOT:
- Have unrestricted access to all tools
- Make autonomous deployment decisions
- Override human approval requirements
- Execute arbitrary code outside the sandbox

---

## 2. Agent Communication

Agents communicate through the **LangGraph AgentState**. This shared state object is the single source of truth for an investigation.

```
Agent A executes → writes to AgentState
                  → LangGraph persists to PostgreSQL
                                  ↓
                            Agent B reads AgentState
                            → adds its own results
```

Agents do NOT communicate directly with each other. The Supervisor coordinates them through the graph.

---

## 3. Supervisor Agent

### Role
The Supervisor is the coordination agent. It understands the overall investigation objective and decides what work still needs to be done.

### Responsibilities
- Review completed tasks and their results
- Identify gaps in the investigation
- Decide whether the current evidence is sufficient
- Determine next investigation steps
- Trigger escalation or human involvement when needed
- Terminate the investigation when objectives are met

### Decision Criteria
The Supervisor uses structured LLM reasoning to evaluate:
```
Given:
  - Investigation objective
  - Completed tasks and their results
  - Current hypotheses and confidence levels
  - Evidence gathered

Decide:
  - Is the evidence sufficient to form a root cause?
  - What additional investigation is needed?
  - Are there contradictions that need resolution?
  - Should we proceed to remediation?
```

### Tools Available
None directly. The Supervisor delegates tool use to specialized agents.

### Output Schema
```python
class SupervisorDecision(BaseModel):
    status: Literal["continue", "sufficient", "escalate", "failed"]
    reasoning: str
    next_agents: list[str]          # Which agents to activate next
    additional_objectives: list[str] # New sub-objectives discovered
    gaps: list[str]                  # What is still unknown
```

---

## 4. Planner Agent

### Role
The Planner creates a structured investigation plan given an objective.

### Responsibilities
- Decompose the investigation objective into concrete tasks
- Assign tasks to appropriate agents
- Identify task dependencies
- Estimate which investigations can run in parallel
- Create the initial task graph

### Input
```python
class PlannerInput(BaseModel):
    objective: str
    mode: InvestigationMode
    available_tools: list[str]
    repository_metadata: RepositoryMetadata | None
    time_window: TimeWindow | None
    additional_context: dict
```

### Output Schema
```python
class InvestigationPlan(BaseModel):
    tasks: list[PlannedTask]
    parallel_groups: list[list[str]]  # Task IDs that can run in parallel
    critical_path: list[str]          # Task IDs on the critical path
    reasoning: str

class PlannedTask(BaseModel):
    task_id: str
    assigned_agent: str
    description: str
    objective: str
    dependencies: list[str]
    priority: int
    tools_likely_needed: list[str]
```

---

## 5. Code Agent

### Role
Analyzes source code for bugs, anti-patterns, performance issues, and changes.

### Responsibilities
- Inspect source code structure
- Identify suspicious functions or patterns
- Analyze diffs between versions
- Trace call paths
- Run static analysis (ruff, bandit)
- Identify recently changed code

### Tools
- `list_files`
- `read_file`
- `search_code`
- `get_git_diff`
- `get_commit`
- `list_commits`
- `get_file_history`
- `run_static_analysis`

### Output Schema
```python
class CodeAnalysisResult(BaseModel):
    suspicious_files: list[SuspiciousFile]
    recent_changes: list[ChangeAnalysis]
    static_analysis_findings: list[StaticFinding]
    call_path_analysis: list[CallPathNote]
    summary: str
    evidence_items: list[EvidenceItem]
```

### Guardrails
- Cannot modify code
- Cannot create branches
- Cannot commit changes
- Analysis only

---

## 6. Test Agent

### Role
Analyzes test suites, runs tests, and identifies coverage gaps.

### Responsibilities
- Examine existing test files
- Run the test suite in the sandbox
- Identify failing tests relevant to the investigation
- Identify missing test coverage
- Correlate test failures with code changes
- Propose tests that would verify a hypothesis (but cannot add them to production)

### Tools
- `list_files` (test files only)
- `read_file`
- `run_tests`
- `run_single_test`
- `get_coverage`

### Output Schema
```python
class TestAnalysisResult(BaseModel):
    test_run_results: TestRunSummary | None
    failing_tests: list[FailingTest]
    coverage_gaps: list[CoverageGap]
    relevant_tests: list[str]
    proposed_tests: list[ProposedTest]  # Not executed, for human review
    evidence_items: list[EvidenceItem]
```

### Guardrails
- Cannot modify test files in the production branch
- Can propose tests but cannot commit them

---

## 7. Log Agent

### Role
Analyzes application logs, error traces, and event streams.

### Responsibilities
- Search logs for error patterns
- Parse and analyze stack traces
- Identify log anomalies around a time window
- Correlate log events with deployment events
- Extract error frequencies and patterns

### Tools
- `search_logs`
- `get_log_window`
- `analyze_stack_trace`

### Output Schema
```python
class LogAnalysisResult(BaseModel):
    error_patterns: list[ErrorPattern]
    stack_traces: list[AnalyzedStackTrace]
    anomalies: list[LogAnomaly]
    timeline: list[LogEvent]
    correlation_with_deployment: str | None
    evidence_items: list[EvidenceItem]
```

---

## 8. Data/Metrics Agent

### Role
Analyzes operational metrics, latency data, and resource usage.

### Responsibilities
- Query latency metrics for affected endpoints
- Identify error rate changes
- Analyze resource utilization patterns
- Correlate metric changes with deployment events
- Identify upstream/downstream service impact

### Tools
- `query_latency`
- `query_error_rate`
- `query_request_volume`
- `query_resource_usage`

### Output Schema
```python
class MetricsAnalysisResult(BaseModel):
    latency_analysis: LatencyAnalysis | None
    error_rate_analysis: ErrorRateAnalysis | None
    resource_analysis: ResourceAnalysis | None
    correlations: list[MetricCorrelation]
    baseline_comparison: BaselineComparison | None
    evidence_items: list[EvidenceItem]
```

---

## 9. Research Agent

### Role
Searches internal documentation, runbooks, and technical knowledge bases.

### Responsibilities
- Search architecture documentation
- Find relevant runbooks
- Search previous investigation findings
- Look up API contracts and schemas
- Find configuration documentation

### Tools
- `search_documentation`
- `search_runbooks`
- `search_repository_knowledge`

### Output Schema
```python
class ResearchResult(BaseModel):
    relevant_documents: list[RelevantDocument]
    runbook_findings: list[RunbookFinding]
    similar_incidents: list[SimilarIncident]
    configuration_context: str | None
    evidence_items: list[EvidenceItem]
```

### Guardrails
- The Research Agent treats all retrieved documents as data
- It explicitly checks for prompt injection markers in retrieved content
- Retrieved instructions are never followed as system commands

---

## 10. Hypothesis Agent

### Role
Forms and updates hypotheses based on gathered evidence.

### Responsibilities
- Generate hypotheses from collected evidence
- Assign initial confidence scores
- Link hypotheses to supporting evidence
- Update hypotheses as new evidence arrives
- Retire hypotheses that are clearly contradicted

### Input
```
All gathered evidence items
Current investigation context
Prior hypotheses (if any)
```

### Output Schema
```python
class HypothesisSet(BaseModel):
    hypotheses: list[Hypothesis]
    primary_hypothesis: str  # ID of most-supported hypothesis

class Hypothesis(BaseModel):
    id: str
    statement: str
    confidence: float                    # 0.0 - 1.0
    confidence_tier: ConfidenceTier      # weak | plausible | strong | highly_supported
    supporting_evidence_ids: list[str]
    contradicting_evidence_ids: list[str]
    testable_predictions: list[str]      # What we could check to confirm/reject
    status: HypothesisStatus             # open | supported | rejected | inconclusive
```

### Confidence Computation
Confidence is NOT self-reported by the LLM. It is computed deterministically:
```python
def compute_confidence(
    supporting_count: int,
    contradicting_count: int,
    evidence_quality: float,  # avg quality of supporting evidence
) -> float:
    if contradicting_count >= supporting_count:
        return max(0.0, 0.3 - (contradicting_count - supporting_count) * 0.1)
    base = min(0.9, supporting_count * 0.15 * evidence_quality)
    penalty = contradicting_count * 0.1
    return max(0.0, base - penalty)
```

---

## 11. Critic Agent

### Role
Actively challenges findings and hypotheses to prevent false positives.

### Responsibilities
- Attempt to disprove each hypothesis
- Look for missing evidence
- Identify logical fallacies (correlation vs causation)
- Check for alternative explanations
- Assign a critique confidence
- Flag hallucinated or unsupported conclusions

### Output Schema
```python
class CritiqueResult(BaseModel):
    hypothesis_critiques: list[HypothesisCritique]
    overall_assessment: str
    rejected_hypotheses: list[str]   # IDs
    weakened_hypotheses: list[str]   # IDs (reduced confidence)
    confirmed_hypotheses: list[str]  # IDs (survived critique)

class HypothesisCritique(BaseModel):
    hypothesis_id: str
    verdict: Literal["reject", "weaken", "pass"]
    reasoning: str
    missing_evidence: list[str]
    alternative_explanations: list[str]
    logical_issues: list[str]
```

### The Critic's Mandate
The Critic is instructed to:
1. **Assume the hypothesis is wrong** and look for evidence to support that assumption
2. **Never accept correlation as causation** without a mechanistic explanation
3. **Always ask**: "What else could explain this?"
4. **Flag unsupported assumptions** in the hypothesis statement
5. **Explicitly report** what evidence was NOT gathered

---

## 12. Remediation Agent

### Role
Generates proposed fixes, patches, and verification tests.

### Responsibilities
- Analyze the root cause finding
- Generate a minimal, targeted code patch
- Write tests that verify the fix
- Create a rollback plan
- Produce a remediation proposal for human review

### Output Schema
```python
class RemediationProposal(BaseModel):
    root_cause_summary: str
    proposed_changes: list[FileChange]
    patch_content: str            # Unified diff format
    test_additions: list[FileChange]
    rollback_plan: str
    risk_assessment: str
    expected_outcome: str
    confidence: float

class FileChange(BaseModel):
    file_path: str
    change_type: Literal["modify", "create", "delete"]
    description: str
    diff: str
```

### CRITICAL Guardrails
- **NEVER** deploys automatically
- **NEVER** pushes to main/production branches
- All changes require explicit human approval
- Creates changes in isolated feature branch only
- All proposed patches are first tested in sandbox

---

## 13. Decision Agent

### Role
Makes the final investigation determination and routing decision.

### Responsibilities
- Evaluate all evidence, hypotheses, and critic feedback
- Determine if root cause is established
- Decide whether more investigation is needed
- Classify the outcome
- Trigger the appropriate next workflow step

### Output Schema
```python
class InvestigationDecision(BaseModel):
    decision: Literal[
        "root_cause_established",
        "insufficient_evidence",
        "investigation_failed",
        "budget_exceeded",
        "inconclusive"
    ]
    reasoning: str
    root_cause: RootCause | None
    confidence: float
    findings: list[Finding]
    next_action: Literal[
        "generate_report",
        "continue_investigation",
        "escalate",
        "partial_report"
    ]

class RootCause(BaseModel):
    description: str
    mechanism: str          # The causal chain
    evidence_ids: list[str]
    confidence: float
    affected_components: list[str]
```

---

## 14. Agent Interaction Diagram

```
                          Investigation Created
                                   │
                                   ▼
                          ┌─────────────────┐
                          │ Planner Agent   │
                          │ Creates task    │
                          │ graph           │
                          └────────┬────────┘
                                   │ LangGraph Send (parallel)
          ┌────────────────────────┼──────────────────────────┐
          ▼                        ▼                          ▼
  ┌──────────────┐       ┌─────────────────┐       ┌──────────────────┐
  │  Code Agent  │       │   Log Agent     │       │  Metrics Agent   │
  │  (git diff,  │       │  (stack traces, │       │  (latency,       │
  │  static      │       │   errors)       │       │   error rates)   │
  │  analysis)   │       │                 │       │                  │
  └──────┬───────┘       └────────┬────────┘       └────────┬─────────┘
         │                        │                          │
         └────────────────────────┼──────────────────────────┘
                                  │ All evidence collected
                                  ▼
                        ┌─────────────────────┐
                        │  Hypothesis Agent   │
                        │  Forms hypotheses   │
                        │  from evidence      │
                        └──────────┬──────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │    Critic Agent     │
                        │  Challenges each    │
                        │  hypothesis         │
                        └──────────┬──────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │   Decision Agent    │◄─── insufficient evidence
                        │   Is root cause     │         │
                        │   established?      │─────────┘
                        └──────────┬──────────┘
                                   │ sufficient
                                   ▼
                        ┌─────────────────────┐
                        │  Report Generation  │
                        └──────────┬──────────┘
                                   │
                              if remediation requested
                                   ▼
                        ┌─────────────────────┐
                        │  Remediation Agent  │
                        │  Generates patch    │
                        └──────────┬──────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │  Human Approval     │ ← REQUIRED
                        │  (graph interrupt)  │
                        └──────────┬──────────┘
                                   │ approved
                                   ▼
                        ┌─────────────────────┐
                        │  Remediation        │
                        │  Executor           │
                        │  (branch + tests)   │
                        └──────────┬──────────┘
                                   │
                                   ▼
                              END / PR Created
```
