"""Built-in compound report preset definitions."""

PRESETS = {
    "first-contact": [
        {"title": "Map", "command": ["map"]},
        {"title": "Health", "command": ["health"]},
        {"title": "Weather", "command": ["weather", "-n", "10"]},
        {"title": "Layers", "command": ["layers"]},
        {"title": "Coupling", "command": ["coupling", "-n", "10"]},
    ],
    "security": [
        {"title": "Risk (auth/session)", "command": ["risk", "--domain", "auth,session", "-n", "20"]},
        {"title": "Coverage Gaps", "command": ["coverage-gaps", "--gate", "requireUser,requireAuth", "--scope", "app/routes/**"]},
        {"title": "Secret Grep", "command": ["grep", "password|secret|token", "--source-only", "-n", "30"]},
        {"title": "Fan", "command": ["fan", "-n", "20"]},
    ],
    "pre-pr": [
        {"title": "PR Risk", "command": ["pr-risk"]},
        {"title": "Diff Blast Radius", "command": ["diff"]},
        {"title": "Coupling (staged)", "command": ["coupling", "--staged"]},
    ],
    "refactor": [
        {"title": "Weather", "command": ["weather", "-n", "20"]},
        {"title": "Dead Summary", "command": ["dead", "--summary"]},
        {"title": "Fan", "command": ["fan", "-n", "20"]},
        {"title": "Health", "command": ["health"]},
    ],
    "health": [
        {"title": "Layers", "command": ["layers"]},
        {"title": "Health", "command": ["health"]},
        {"title": "Clusters", "command": ["clusters"]},
        {"title": "Coupling", "command": ["coupling", "-n", "10"]},
        {"title": "Fan", "command": ["fan", "-n", "20"]},
    ],
}
