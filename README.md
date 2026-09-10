# research-core

Shared research engine for Tender Designer, Internet Pricing, and Should-Cost Intelligence.

`research-core` owns reusable research mechanics. Each application keeps its domain-specific prompts, policy, compliance rules, pricing logic and estimator behaviour.

## Current v0.2.0 scope

- Generic quality-led research loop
- Candidate pooling and unread-candidate lifecycle
- Dynamic page/round budgeting with hard safety ceilings
- Stagnation and stop/continue decisions
- Generic lexical/technical candidate ranking
- Numeric/specification-aware ranking for engineering and product searches
- Commercial evidence signals for prices, awards, BOQs, quotations, invoices and transaction data
- Candidate ranking based on returned title/snippet/URL rather than leaking the originating query into relevance scoring
- Optional embedding similarity weighting
- Domain diversity
- Shared evidence quality levels: `strong`, `useful`, `weak`, `reject`
- Evidence-preserving passage extraction that retains concrete price/award passages alongside technical matches
- Evidence-ledger formatting

Search providers, HTTP/PDF/browser retrieval and app-specific LLM prompts remain in the applications for the first migration phase. They can be moved behind core interfaces later without forcing all three applications to change at once.

## Architecture

```text
                    research-core
                         |
       +-----------------+-----------------+
       |                 |                 |
Tender Designer    Internet Pricing   Should-Cost Intelligence
Tender policy      Pricing policy     Deterministic estimator policy
```

The shared `ResearchEngine` receives application callbacks for:

```text
search -> rank -> read -> source review -> coverage assessment
```

The core owns the loop around those callbacks: candidate pooling, batches, dynamic depth, stagnation, and stopping.

## Install from GitHub

Pin applications to a known commit or release rather than `main`:

```text
research-core @ git+https://github.com/zageabb/research-core.git@<commit-or-tag>
```

Normal application deployment remains:

```bash
git pull
python -m pip install -r requirements.txt
```

`pip` installs the pinned research-core revision automatically.

For local joint development:

```bash
pip install -e ../research-core
```

## Migration order

1. Tender Designer: ranking and dynamic-depth lifecycle first.
2. Internet Pricing: shared dynamic depth, evidence quality and passage handling.
3. Should-Cost Intelligence: shared ranking/embedding/depth while preserving its canonical specification and deterministic evidence scoring.
4. Later: common fetch/cache/browser and search-provider interfaces after all three consumers are stable.
