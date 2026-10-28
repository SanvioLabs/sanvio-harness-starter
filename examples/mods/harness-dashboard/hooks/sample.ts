// What scripts/dashboard_data.py's build() printed in tests/test_dashboard_data.py's Sample. Don't edit it:
// UPDATE_SAMPLE=1 python3 -m unittest tests.test_dashboard_data.Sample writes it again.
import type { Doc } from '../types'

export const SAMPLE: Doc = {
  "activity": {
    "agents": {
      "reviewer": 1
    },
    "asks": 1,
    "commands": {
      "standup": 1
    },
    "guard_refusals": {
      "credential-file": 2
    },
    "skills": {
      "learn": 1,
      "review-pr": 2
    }
  },
  "conversations": {
    "harness": {
      "by_day": [
        {
          "day": "2026-10-15",
          "tokens": 0
        },
        {
          "day": "2026-10-16",
          "tokens": 0
        },
        {
          "day": "2026-10-17",
          "tokens": 0
        },
        {
          "day": "2026-10-18",
          "tokens": 0
        },
        {
          "day": "2026-10-19",
          "tokens": 0
        },
        {
          "day": "2026-10-20",
          "tokens": 10
        },
        {
          "day": "2026-10-21",
          "tokens": 0
        },
        {
          "day": "2026-10-22",
          "tokens": 0
        },
        {
          "day": "2026-10-23",
          "tokens": 0
        },
        {
          "day": "2026-10-24",
          "tokens": 100
        },
        {
          "day": "2026-10-25",
          "tokens": 0
        },
        {
          "day": "2026-10-26",
          "tokens": 0
        },
        {
          "day": "2026-10-27",
          "tokens": 0
        }
      ],
      "by_model": {
        "m-a": {
          "cache_reads": 4,
          "cache_writes": 3,
          "input": 1,
          "output": 2,
          "total": 10
        },
        "m-b": {
          "cache_reads": 40,
          "cache_writes": 30,
          "input": 10,
          "output": 20,
          "total": 100
        }
      },
      "sessions": 1
    },
    "loop": {
      "by_day": [
        {
          "day": "2026-10-15",
          "tokens": 0
        },
        {
          "day": "2026-10-16",
          "tokens": 0
        },
        {
          "day": "2026-10-17",
          "tokens": 0
        },
        {
          "day": "2026-10-18",
          "tokens": 0
        },
        {
          "day": "2026-10-19",
          "tokens": 0
        },
        {
          "day": "2026-10-20",
          "tokens": 0
        },
        {
          "day": "2026-10-21",
          "tokens": 0
        },
        {
          "day": "2026-10-22",
          "tokens": 0
        },
        {
          "day": "2026-10-23",
          "tokens": 0
        },
        {
          "day": "2026-10-24",
          "tokens": 0
        },
        {
          "day": "2026-10-25",
          "tokens": 0
        },
        {
          "day": "2026-10-26",
          "tokens": 10000
        },
        {
          "day": "2026-10-27",
          "tokens": 0
        }
      ],
      "by_model": {
        "m-a": {
          "cache_reads": 4000,
          "cache_writes": 3000,
          "input": 1000,
          "output": 2000,
          "total": 10000
        }
      },
      "sessions": 1
    }
  },
  "evals": {
    "reviewer": {
      "changed": [],
      "failing": 1,
      "failing_cases": [
        "03-c"
      ],
      "flaky": 1,
      "newest_change": null,
      "saved": "2026-10-25T09:00:00+00:00",
      "stable": 1,
      "stale": true,
      "why": "folder missing"
    },
    "security-reviewer": {
      "changed": [],
      "failing": 0,
      "failing_cases": [],
      "flaky": 0,
      "newest_change": null,
      "saved": "2026-10-26T09:00:00+00:00",
      "stable": 1,
      "stale": true,
      "why": "folder missing"
    }
  },
  "generated": "2026-10-27T12:00:00+00:00",
  "loop_rework": {
    "merged": 2,
    "pull_requests": [
      {
        "merges_from_base": 1,
        "number": 102,
        "other_commits": 1,
        "title": "Fixed by hand"
      }
    ],
    "reworked": 1
  },
  "loop_spend": {
    "by_day": [
      {
        "cost_usd": 0.0,
        "day": "2026-10-15",
        "tokens": 0
      },
      {
        "cost_usd": 2.0,
        "day": "2026-10-16",
        "tokens": 1000
      },
      {
        "cost_usd": 0.0,
        "day": "2026-10-17",
        "tokens": 0
      },
      {
        "cost_usd": 0.0,
        "day": "2026-10-18",
        "tokens": 0
      },
      {
        "cost_usd": 0.0,
        "day": "2026-10-19",
        "tokens": 0
      },
      {
        "cost_usd": 0.0,
        "day": "2026-10-20",
        "tokens": 0
      },
      {
        "cost_usd": 0.0,
        "day": "2026-10-21",
        "tokens": 0
      },
      {
        "cost_usd": 0.25,
        "day": "2026-10-22",
        "tokens": 10
      },
      {
        "cost_usd": 0.0,
        "day": "2026-10-23",
        "tokens": 0
      },
      {
        "cost_usd": 0.0,
        "day": "2026-10-24",
        "tokens": 0
      },
      {
        "cost_usd": 0.0,
        "day": "2026-10-25",
        "tokens": 0
      },
      {
        "cost_usd": 0.0,
        "day": "2026-10-26",
        "tokens": 0
      },
      {
        "cost_usd": 1.75,
        "day": "2026-10-27",
        "tokens": 305
      }
    ],
    "by_issue": {
      "app/issue-3": {
        "cost_usd": 0.25,
        "tokens": 5
      },
      "issue-7": {
        "cost_usd": 1.75,
        "tokens": 310
      },
      "issue-9": {
        "cost_usd": 2.0,
        "tokens": 1000
      }
    },
    "by_model": {
      "claude-a": {
        "cost_usd": 1.5,
        "label": "claude-a",
        "tokens": 115
      },
      "claude-b": {
        "cost_usd": 2.0,
        "label": "claude-b",
        "tokens": 1000
      },
      "null": {
        "cost_usd": 0.5,
        "label": "model not recorded",
        "tokens": 200
      }
    },
    "by_step": {
      "build": {
        "cost_usd": 0.5,
        "tokens": 200
      },
      "plan": {
        "cost_usd": 3.25,
        "tokens": 1110
      },
      "review": {
        "cost_usd": 0.25,
        "tokens": 5
      }
    },
    "cost_per_pr": 2.0,
    "first_run": "2026-10-16",
    "last_7_days": {
      "cost_usd": 2.0,
      "tokens": 315
    },
    "since": {
      "cost_usd": 4.0,
      "tokens": 1315
    },
    "today": {
      "cost_usd": 1.75,
      "tokens": 305
    }
  },
  "loop_throughput": {
    "by_state": {
      "blocked": 1,
      "building": 1,
      "pr": 2
    },
    "issues": 4,
    "more_than_one_round": 2,
    "rounds": {
      "app/issue-3": 1,
      "issue-12": 1,
      "issue-7": 2,
      "issue-9": 3
    }
  },
  "since": "2026-10-15",
  "waiting": {
    "blocked": [
      {
        "issue": "issue-9",
        "note": "sentinel-zq7",
        "number": 9,
        "title": "sentinel-zq7",
        "updated": null
      }
    ],
    "pull_requests": [
      {
        "checks": "pass",
        "conflicts": false,
        "draft": false,
        "hours_waited": 2.5,
        "loop_issue": 264,
        "number": 41,
        "opened": "2026-10-27T09:30:00Z",
        "title": "PR 41 sentinel-zq7"
      },
      {
        "checks": "fail",
        "conflicts": true,
        "draft": true,
        "hours_waited": 48.0,
        "loop_issue": null,
        "number": 42,
        "opened": "2026-10-25T12:00:00Z",
        "title": "PR 42 sentinel-zq7"
      },
      {
        "checks": "pending",
        "conflicts": null,
        "draft": false,
        "hours_waited": 1.0,
        "loop_issue": null,
        "number": 43,
        "opened": "2026-10-27T11:00:00Z",
        "title": "PR 43 sentinel-zq7"
      },
      {
        "checks": "pending",
        "conflicts": false,
        "draft": false,
        "hours_waited": 1.0,
        "loop_issue": 8,
        "number": 44,
        "opened": "2026-10-27T11:00:00Z",
        "title": "PR 44 sentinel-zq7"
      },
      {
        "checks": "fail",
        "conflicts": false,
        "draft": false,
        "hours_waited": 1.0,
        "loop_issue": null,
        "number": 45,
        "opened": "2026-10-27T11:00:00Z",
        "title": "PR 45 sentinel-zq7"
      },
      {
        "checks": null,
        "conflicts": false,
        "draft": false,
        "hours_waited": 1.0,
        "loop_issue": null,
        "number": 46,
        "opened": "2026-10-27T11:00:00Z",
        "title": "PR 46 sentinel-zq7"
      }
    ]
  }
}
