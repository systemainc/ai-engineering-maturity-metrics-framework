window.DASHBOARD_DATA = {
  "meta": {
    "org": "Test Org",
    "engineers": 5,
    "teams": 3,
    "divisions": 2,
    "periodCurrent": "2026-Q2",
    "periodPrior": "2026-Q1",
    "sourceErrors": [],
    "sourcesRun": 11,
    "sourcesFailed": 0
  },
  "LEVELS": [
    { "n": 1, "key": "l1", "name": "Exploring" },
    { "n": 2, "key": "l2", "name": "Piloting" },
    { "n": 3, "key": "l3", "name": "Scaling" },
    { "n": 4, "key": "l4", "name": "Optimizing" }
  ],
  "DIMENSIONS": [
    { "id": "adoption", "name": "AI Adoption & Fluency", "orgLevel": 3, "orgTrend": 1, "orgHi": "60% weekly active usage · 66.7% ai-assisted pr share", "insufficientData": false },
    { "id": "flow", "name": "Delivery Flow", "orgLevel": 2, "orgTrend": 0, "orgHi": "0.2 deploys / week (median) · 169 hrs lead time", "insufficientData": false },
    { "id": "spend", "name": "AI Spend Efficiency", "orgLevel": 3, "orgTrend": 0, "orgHi": "60% credit utilization · $433.3/mo spend / active user", "insufficientData": false },
    { "id": "quality", "name": "Quality & Risk Automation", "orgLevel": 3, "orgTrend": 1, "orgHi": "66.7% ai-generated test coverage · 66.7% ai review gate coverage", "insufficientData": false },
    { "id": "health", "name": "Codebase Health", "orgLevel": 3, "orgTrend": 0, "orgHi": "67.9/100 composite score", "insufficientData": false }
  ],
  "DIVISIONS": [
    {
      "name": "Payments & Billing", "teams": 2, "engineers": 3,
      "dims": {
        "adoption": { "level": 3, "trend": 1, "m": [["Weekly active usage", "66.7%", "+33.4"], ["AI-assisted PR share", "50%", "+50.0"], ["Agentic workflow training", "33.3%", "+0.0"]], "insufficientData": false },
        "flow": { "level": 2, "trend": 0, "m": [["Deploys / week (median)", "0.2", "+0.1"], ["Lead time", "169 hrs", "-48.0"], ["Change failure rate", "50%", "+50.0"], ["MTTR", "6 hrs", "-14.0"]], "insufficientData": false },
        "spend": { "level": 3, "trend": 0, "m": [["Credit utilization", "66.7%", "+0.0"], ["Spend / active user", "$450/mo", "-150.0"]], "insufficientData": false },
        "quality": { "level": 3, "trend": 1, "m": [["AI-generated test coverage", "50%", "+50.0"], ["AI review gate coverage", "50%", "n/a"], ["Critical/high vulns escaped", "1", "+1.0"]], "insufficientData": false },
        "health": { "level": 3, "trend": 0, "m": [["Composite score", "62.8/100", "+7.0"]], "insufficientData": false }
      }
    },
    {
      "name": "Core Platform & Infra", "teams": 1, "engineers": 2,
      "dims": {
        "adoption": { "level": 3, "trend": 1, "m": [["Weekly active usage", "50%", "+50.0"], ["AI-assisted PR share", "100%", "+100.0"], ["Agentic workflow training", "50%", "+0.0"]], "insufficientData": false },
        "flow": { "level": 2, "trend": 0, "m": [["Deploys / week (median)", "0.1", "+0.0"], ["Lead time", "n/a", "n/a"], ["Change failure rate", "0%", "+0.0"], ["MTTR", "n/a", "n/a"]], "insufficientData": false },
        "spend": { "level": 3, "trend": 0, "m": [["Credit utilization", "50%", "+0.0"], ["Spend / active user", "$400/mo", "+200.0"]], "insufficientData": false },
        "quality": { "level": 4, "trend": 1, "m": [["AI-generated test coverage", "100%", "+100.0"], ["AI review gate coverage", "100%", "n/a"], ["Critical/high vulns escaped", "0", "-1.0"]], "insufficientData": false },
        "health": { "level": 4, "trend": 1, "m": [["Composite score", "73/100", "+4.8"]], "insufficientData": false }
      }
    }
  ]
};
