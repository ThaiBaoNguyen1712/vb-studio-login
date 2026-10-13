# E2E Test Infra: VB-Login Native Browser Process Execution

## Test Philosophy
- Opaque-box, requirement-driven. Derived from `ORIGINAL_REQUEST.md` and user-facing specifications, not internal private structures.
- Methodology: Category-Partition + Boundary Value Analysis (BVA) + Pairwise Combinatorial Testing + Real-World Workload Testing.
- Test runner: Python standard library `unittest` (`python -m unittest discover -s tests -p "test_*.py"`), requiring 0 extra test dependencies.

## Feature Inventory
| # | Feature | Source | Tier 1 (Feature) | Tier 2 (Boundary) | Tier 3 (Cross-Feature) |
|---|---------|--------|:----------------:|:-----------------:|:----------------------:|
| 1 | Windows Browser Detection (Chrome/Edge) | ORIGINAL_REQUEST §R1 | ≥5 | ≥5 | ✓ |
| 2 | Native Process Execution (subprocess.Popen) | ORIGINAL_REQUEST §R1 | ≥5 | ≥5 | ✓ |
| 3 | Process Lifecycle & PID Tracking | ORIGINAL_REQUEST §R1 | ≥5 | ≥5 | ✓ |
| 4 | Multi-Profile Concurrency & Isolation | ORIGINAL_REQUEST §R2 | ≥5 | ≥5 | ✓ |
| 5 | Safe SQLite Snapshot & Lock Avoidance | ORIGINAL_REQUEST §R3 | ≥5 | ≥5 | ✓ |
| 6 | Windows DPAPI & AES-256-GCM Decryption | ORIGINAL_REQUEST §R3 | ≥5 | ≥5 | ✓ |
| 7 | Vault Storage & Session Integration | ORIGINAL_REQUEST §R3 | ≥5 | ≥5 | ✓ |
| 8 | Dependency & Packaging Cleanup | ORIGINAL_REQUEST §R4 | ≥5 | ≥5 | ✓ |

## Test Architecture
- **Runner**: `python -m unittest discover -s tests -p "test_*.py"`
- **Test Modules**:
  - `tests/test_tier1_features.py`: Feature isolation tests (≥40 tests across 8 features).
  - `tests/test_tier2_boundaries.py`: Boundary, corner cases, error handling, edge cases (≥40 tests).
  - `tests/test_tier3_pairwise.py`: Cross-feature interactions and state transitions (≥8 tests).
  - `tests/test_tier4_scenarios.py`: Real-world end-to-end application scenarios (≥5 tests).
- **Semantics**: Exit code 0 indicates all tests pass. Detailed test failure reports for any assertion failure.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | Multi-Channel Launch, Independent Navigation & Clean Shutdown | F1, F2, F3, F4 | High |
| 2 | Live Session Extraction, DPAPI Decryption & Vault Persistence | F5, F6, F7 | High |
| 3 | Concurrent Browser Execution with Simultaneous Session Release | F2, F3, F4, F7 | High |
| 4 | Browser Force Close via Taskkill & Snapshot Recovery | F3, F5, F6 | Medium |
| 5 | Full WebBridge & UI Lifecycle Simulation (No Playwright Traces) | F1, F2, F3, F4, F8 | High |

## Coverage Thresholds
- Tier 1: ≥5 per feature (≥40 test cases)
- Tier 2: ≥5 per feature (≥40 test cases)
- Tier 3: pairwise coverage (≥8 test cases)
- Tier 4: realistic application scenarios (≥5 test cases)
- **Total Minimum**: ≥93 test cases
