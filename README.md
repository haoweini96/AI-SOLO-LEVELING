# AI Solo Leveling

**Gamified AI/ML learning platform inspired by Solo Leveling.** Track your knowledge through an interactive tech tree, earn XP, level up from E-Rank to Shadow Monarch, and master AI/ML concepts through a quest-driven learning system powered by Claude.

Transform your learning journey: start as a low-rank hunter, gradually awaken your potential, and work toward becoming a Shadow Monarch in AI/ML mastery.

---

## Features

### Tech Tree — 46-Node Knowledge Graph
- **6 Major Domains**: Foundations, Deep Learning, LLM & Applications, AI Agents, AI Engineering, AI Products
- **15+ Sub-Branches**: Math & Statistics, Classical ML, Neural Networks, Computer Vision, NLP, LLM Fundamentals, RAG, Agent Development, ML Systems, API Integration, and more
- **Interactive Radial Visualization**: D3.js-powered tech tree showing locked → unlocked → mastered nodes
- **Knowledge Dimensions**: Each concept has structured coverage dimensions (fundamentals, application, advanced theory) evaluated by Claude

### Knowledge Feed
- **Curated Articles**: Aggregated from RSS feeds, Medium, Twitter, and Hacker News
- **AI Summaries**: Claude-powered summaries and key takeaway extraction
- **One-Click Capture**: Save articles directly to your knowledge feed
- **Search & Filter**: Find content by topic, branch, or date

### Quest System
- **Dynamic Quests**: AI-generated learning tasks for each tech tree node
- **Knowledge Dimensions**: Each concept has 3-5 multi-faceted coverage areas
- **AI Evaluation**: Claude evaluates your learning coverage against each dimension
- **Progress Tracking**: Visual indicators for locked → in_progress → lit → mastered states

### Chrome Extension
- **Claude.ai Integration**: One-click capture from Claude conversations
- **Intelligent Parsing**: Auto-extracts knowledge context from your conversations
- **Tech Tree Mapping**: AI maps captured content to 1-3 relevant tech tree nodes
- **Instant Linking**: Knowledge automatically surfaces in your tree and feed

### Study Analysis Engine
- **Article Analysis**: Deep analysis with AI-extracted key concepts, learning outcomes
- **Video Annotation**: Extract transcripts, analyze complexity, map to tech tree nodes
- **Smart Highlighting**: Mark important passages and auto-generate study notes
- **Export to Notion-style Notes**: Structured study materials for spaced repetition

### Spaced Repetition System
- **SM-2 Algorithm**: Adaptive scheduling based on your performance
- **AI-Generated Quizzes**: Claude creates contextual questions from your learned material
- **Review Tracking**: Track your review history and identify weak knowledge areas
- **Streak Bonuses**: Earn XP multipliers for consistent daily reviews

### Hunter Profile — Solo Leveling Rank System
```
E-Rank (Levels 1-10)    → Awakened Hunter
D-Rank (Levels 11-20)   → Promising Talent
C-Rank (Levels 21-35)   → Capable Hunter
B-Rank (Levels 36-50)   → Guild Core Member
A-Rank (Levels 51-65)   → Elite Hunter
S-Rank (Levels 66-80)   → Highest Rank
National Level (81-95)  → Government Power
Shadow Monarch (96-100) → Supreme Authority
```

- **XP Progression**: Earn XP for learning, reviewing, source collection, and quest completion
- **Level-Up Rewards**: Unlock new content and UI features at each milestone
- **Rank-Specific Achievements**: 21+ achievements including domain mastery, review streaks, and rank breakthroughs
- **Leaderboard Integration**: Compare progress with other learners

### XP & Achievement System
- **Earn XP For**:
  - Linking knowledge sources (+50-200 XP)
  - Completing reviews (+10-100 XP based on difficulty)
  - Mastering concepts (+200-500 XP)
  - Maintaining study streaks (+50-1000 XP)
  - Completing branch/domain achievements (+150-500 XP bonus)

- **21 Achievements** including:
  - First Awakening — Light up your first concept
  - Weekly Warrior — 7-day review streak
  - Omniscient — Master the entire tech tree
  - Shadow Monarch — Reach level 100
  - Domain Conqueror — Complete all concepts in a branch

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Browser (Solo Leveling SPA)                   │
│        (index.html: Feed + Study + Knowledge Tree + Profile)    │
└────────────────────────┬────────────────────────────────────────┘
                         │ fetch('/api/...')
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                   Flask API Server (port 8081)                  │
│                                                                   │
│  ├── /api/knowledge-tree/*     Tech Tree, Quests, Reviews,      │
│  │                              Hunter Profile, Achievements     │
│  │                                                                │
│  ├── /api/knowledge/*          Knowledge Feed, Articles,        │
│  │                              Saved Sources, Summarization    │
│  │                                                                │
│  └── /api/study/*              Article/Video Analysis,          │
│                                 Highlights, Transcripts          │
└────────────┬─────────────────────────────────────────────────┬──┘
             │ JSON file persistence                          │ Claude AI
             ↓                                                 ↓
     ┌──────────────┐                                    Knowledge extraction,
     │  data/*.json │                                    quiz generation,
     │  (no DB)     │                                    coverage evaluation
     └──────────────┘
```

### Data Flow

```
New Learning Source
  (article, video, Claude chat, RSS feed)
        │
        ↓
  AI Classification
  (Claude maps to 1-3 tech tree nodes)
        │
        ↓
  Coverage Evaluation
  (Claude scores against knowledge dimensions)
        │
        ↓
  Update Node Status
  (locked → in_progress → lit → mastered)
        │
        ↓
  Award XP & Check
  (calc XP bonus → check level-up → check achievements)
        │
        ↓
  Update Hunter Profile
  (level, rank, achievements, streaks)
```

### Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | Python 3.10+, Flask | RESTful API, JSON persistence |
| **Frontend** | Vanilla JavaScript, D3.js, Lucide Icons | Interactive SPA, tech tree visualization |
| **AI/ML** | Claude Sonnet 3.5 | Knowledge extraction, quiz generation, coverage evaluation |
| **Data** | JSON files (no database) | Atomic writes, mtime-based caching |
| **Storage** | Local filesystem | Tech tree state, hunter profile, reviews, achievements |

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 16+ (optional, for running media analysis)
- Anthropic API key ([get one free](https://console.anthropic.com/))

### Installation

```bash
# Clone repository
git clone https://github.com/nicobailon/AI-SOLO-LEVELING.git
cd AI-SOLO-LEVELING

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template and add API key
cp .env.example .env
# Edit .env and add: ANTHROPIC_API_KEY=sk-ant-...
```

### Running the Platform

**Terminal 1: Start API server**
```bash
cd /path/to/AI-SOLO-LEVELING
source venv/bin/activate
python3 api_server.py
# Server running on http://localhost:8081
```

**Terminal 2: Open the dashboard**
```bash
# Visit http://localhost:8081/apps/study/
```

### Installing Chrome Extension (Optional)

1. **Enable Developer Mode**
   - Open `chrome://extensions/`
   - Toggle "Developer mode" (top right)

2. **Load the Extension**
   - Click "Load unpacked"
   - Select `/AI-SOLO-LEVELING/apps/study/chrome_ext/knowledge_capture/`

3. **Capture Knowledge from Claude**
   - Navigate to https://claude.ai
   - A "Capture" button appears in the Claude interface
   - Click to save key learnings to your tech tree

---

## Project Structure

```
AI-SOLO-LEVELING/
├── api_server.py                    # Flask API server entry point
├── routes/                          # Flask blueprints (API endpoints)
│   ├── _shared.py                   # Shared utilities, logging, atomic I/O
│   ├── pages.py                     # Static page serving
│   ├── knowledge_tree.py            # Tech Tree, Quests, Reviews, Profile
│   ├── knowledge.py                 # Knowledge Feed, Articles, Sources
│   └── study.py                     # Study analysis (videos, articles)
├── apps/
│   └── study/
│       ├── index.html               # Main SPA (Feed + Study + Tech Tree)
│       ├── study.html               # Article/video detail & analysis
│       ├── knowledge_feed.html      # Knowledge feed page
│       ├── analyze_article.py       # Claude-powered article analysis
│       ├── analyze_video.py         # Video transcript & analysis
│       ├── chrome_ext/              # Chrome extension source
│       │   └── knowledge_capture/   # Claude.ai integration
│       └── knowledge_assets/        # Background images, icons
├── data/                            # JSON persistence (no database)
│   ├── knowledge_tree.json          # Tech tree node state
│   ├── hunter_profile.json          # User profile, XP, rank, streaks
│   ├── knowledge_reviews.json       # Review history (SM-2 scheduling)
│   ├── knowledge_feed.json          # Curated article feed
│   ├── knowledge_saved.json         # User-saved sources
│   └── tech_tree_template.json      # Tech tree structure (6 domains, 46 nodes)
├── assets/                          # Static assets
│   ├── org_map_custom/              # Custom character avatars
│   ├── favicon/                     # Favicon
│   └── logo/                        # Logo assets
├── logs/                            # Server logs
├── .env.example                     # Environment template
├── requirements.txt                 # Python dependencies
└── README.md                        # This file
```

---

## API Reference

### Knowledge Tree Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| **GET** | `/api/knowledge-tree/tech-tree` | Get full tech tree with node states |
| **GET** | `/api/knowledge-tree/hunter-profile` | Get hunter profile (rank, XP, streaks, achievements) |
| **GET** | `/api/knowledge-tree/node/<node_id>` | Get detailed node info (title, description, sources, dimensions) |
| **POST** | `/api/knowledge-tree/add-source` | Link a knowledge source to a node |
| **POST** | `/api/knowledge-tree/capture` | Capture knowledge from external source (Chrome ext, article, video) |
| **POST** | `/api/knowledge-tree/review` | Complete a review session (SM-2 scheduling) |
| **GET** | `/api/knowledge-tree/generate-quests` | Generate learning quests for a node |
| **GET** | `/api/knowledge-tree/recommended-tasks` | Get personalized next steps based on profile |
| **POST** | `/api/knowledge-tree/generate-dimensions` | Generate knowledge coverage dimensions for a node |

### Knowledge Feed Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| **GET** | `/api/knowledge` | Get curated knowledge feed (RSS, Medium, HN) |
| **POST** | `/api/knowledge/refresh` | Rebuild feed from sources |
| **GET** | `/api/knowledge/saved` | Get user-saved articles |
| **POST** | `/api/knowledge/saved/add` | Save an article to collection |
| **POST** | `/api/knowledge/saved/delete` | Remove saved article |
| **POST** | `/api/knowledge/summarize` | Generate AI summary of article |

### Study Analysis Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| **GET** | `/api/study/videos` | Get list of analyzed videos/articles |
| **POST** | `/api/study/analyze` | Trigger analysis on URL or video |
| **GET** | `/api/study/analysis/<video_id>` | Get analysis results (key concepts, learnings) |
| **GET** | `/api/study/status/<video_id>` | Get analysis job status |
| **GET,POST** | `/api/study/highlights` | Get/add study highlights |
| **DELETE,PATCH** | `/api/study/highlights/<id>` | Modify individual highlights |

---

## Learning Path Example

Here's a typical learning journey from E-Rank to S-Rank:

1. **Start: E-Rank Awakening** (Levels 1-10)
   - Add first knowledge source
   - Light up "Linear Algebra" and "Probability" nodes
   - Complete first 5 reviews
   - Earn: "First Awakening" achievement (+50 XP)

2. **D-Rank Progression** (Levels 11-20)
   - Master 3 foundational concepts
   - Complete 20+ reviews
   - Build 7-day review streak
   - Unlock: "Weekly Warrior" achievement (+200 XP)

3. **C-Rank Advancement** (Levels 21-35)
   - Master entire "Math & Statistics" branch
   - Light up 10+ concepts across domains
   - Earn: "Illuminator" achievement (+200 XP)
   - Unlock: "Half the World" at 50% tree completion

4. **B-Rank Breakthrough** (Levels 36-50)
   - Complete full Deep Learning branch
   - 30+ day review streak
   - Earn: "Monthly Monarch" (+1000 XP)

5. **A-Rank Mastery** (Levels 51-65)
   - Master 5 entire sub-branches
   - 50% of tech tree lit up
   - Access "Polymath" achievement (all 6 domains started)

6. **S-Rank Elite** (Levels 66-80)
   - Light up 90%+ of tree
   - Master multiple domains
   - Earn: "Omniscient" achievement (+1000 XP)

7. **National Level** (Levels 81-95)
   - Specialized mastery in 2-3 deep domains
   - Complex quiz performance ≥90%
   - Multiple domain completion achievements

8. **Shadow Monarch** (Levels 96-100)
   - Complete entire tech tree
   - Master all 46 concepts
   - Earn: "Shadow Monarch" achievement (+1000 XP)
   - Ultimate achievement: *ARISE!*

---

## Rank System

| Rank | Levels | Icon | Title (EN) | Title (ZH) |
|------|--------|------|-----------|-----------|
| **E** | 1-10 | ⚡ | Awakened Hunter | 觉醒者 |
| **D** | 11-20 | 🟢 | Promising Talent | 有望的天才 |
| **C** | 21-35 | 🔵 | Capable Hunter | 能力者猎人 |
| **B** | 36-50 | 🟣 | Guild Core | 公会核心 |
| **A** | 51-65 | 🟡 | Elite Hunter | 精英猎人 |
| **S** | 66-80 | 🔴 | Highest Rank | S级猎人 |
| **National** | 81-95 | 👑 | Government Power | 国家权力级 |
| **Shadow** | 96-100 | 🖤 | Shadow Monarch | 暗影君王 |

---

## Key Achievements

### Progression Achievements
- **First Awakening**: Light up your first concept node (+50 XP)
- **Rising Hunter**: Light up 5 concept nodes (+100 XP)
- **Illuminator**: Light up 10 concept nodes (+200 XP)
- **Half the World**: Light up 50% of the tech tree (+500 XP)
- **Omniscient**: Light up the entire tech tree (+1000 XP)

### Mastery Achievements
- **Shadow Extraction**: Master your first concept (+200 XP)
- **Shadow Army**: Master 5 concepts (+500 XP)
- **Domain Conqueror**: Complete all concepts in a branch (+500 XP)

### Review & Learning Achievements
- **Daily Quest**: Complete your first review (+30 XP)
- **Weekly Warrior**: 7-day review streak (+200 XP)
- **Monthly Monarch**: 30-day review streak (+1000 XP)
- **Centurion**: Complete 100 reviews (+500 XP)

### Collection Achievements
- **Knowledge Collector**: Link 10 knowledge sources (+100 XP)
- **Polymath**: Light up nodes in all 6 branches (+300 XP)

### Rank Achievements
- **觉醒** (Awakening): Reach D-Rank (+50 XP)
- **C级突破** (C-Rank Breakthrough): Reach C-Rank (+100 XP)
- **暗影君王** (Shadow Monarch): Reach level 100 (+1000 XP)

---

## Configuration

### Environment Variables (`.env`)

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...        # Claude API key

# Optional (for article fetching / analysis)
OPENAI_API_KEY=sk-...               # For fallback analysis
BING_NEWS_API_KEY=...               # For news aggregation
```

### Tech Tree Customization

Edit `data/tech_tree_template.json` to modify domains, branches, and concepts:

```json
{
  "domains": [
    {
      "id": "foundations",
      "title": "Foundations",
      "branches": [
        {
          "id": "math_stats",
          "title": "Math & Statistics",
          "concepts": [
            {
              "id": "linear_algebra",
              "title": "Linear Algebra",
              "description": "Vectors, matrices, eigenvalues..."
            }
          ]
        }
      ]
    }
  ]
}
```

---

## Development

### Adding a New Tech Tree Concept

1. **Update tech_tree_template.json**
   ```json
   {
     "id": "your_concept_id",
     "title": "Your Concept",
     "description": "Description of the concept",
     "prerequisites": ["concept_id_1"],
     "learning_time_hours": 10
   }
   ```

2. **Define Knowledge Dimensions** (automatically generated by Claude, but can customize)
   ```python
   # In analyze_article.py or manually:
   dimensions = [
     {"name": "fundamentals", "weight": 0.3},
     {"name": "practical_application", "weight": 0.4},
     {"name": "advanced_theory", "weight": 0.3}
   ]
   ```

3. **Test in Development**
   ```bash
   curl http://localhost:8081/api/knowledge-tree/tech-tree
   ```

### Running Tests

```bash
# Analyze a test article
python3 apps/study/analyze_article.py "https://example.com/article"

# Test knowledge tree updates
python3 -m pytest routes/test_knowledge_tree.py -v

# Validate tech tree structure
python3 -c "from routes._shared import load_json; import json; tree = load_json('data/tech_tree_template.json'); print(f'Domains: {len(tree[\"domains\"])}, Total concepts: {sum(len(b[\"concepts\"]) for d in tree[\"domains\"] for b in d[\"branches\"])}')"
```

---

## Performance Tips

### Optimize for Large Knowledge Bases
- **Cache Frequently**: Articles and tech tree data are mtime-cached in memory
- **Async Analysis**: Video/article analysis runs in background with job status polling
- **Incremental Indexing**: Only process new sources on feed refresh

### Reduce API Calls
- **Batch Reviews**: Complete multiple reviews per session
- **Cache Claude Responses**: Analysis results and quiz questions are cached
- **Pre-computed Recommendations**: Suggested next steps updated on schedule

### Monitor Storage
- **Data Directory Size**: `du -sh data/`
- **Archive Old Reviews**: Reviews >30 days old can be moved to `data/archive/`
- **Cleanup Failed Jobs**: Remove incomplete analysis entries from `data/study_analyses/`

---

## Troubleshooting

### API Server Won't Start
```bash
# Check logs
tail -f logs/api_server.log

# Verify port 8081 is free
lsof -i :8081

# Rebuild virtual environment
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Knowledge Feed Empty
```bash
# Manually trigger refresh
curl -X POST http://localhost:8081/api/knowledge/refresh

# Check data file
cat data/knowledge_feed.json | head -20
```

### Claude Analysis Timing Out
- Increase timeout in `routes/study.py` (default: 30s)
- Check ANTHROPIC_API_KEY is valid
- Verify Claude API status at https://status.anthropic.com/

### Tech Tree Not Updating
```bash
# Force reload tech tree
rm data/knowledge_tree.json
curl http://localhost:8081/api/knowledge-tree/tech-tree

# Check for JSON errors
python3 -m json.tool data/knowledge_tree.json | head -20
```

---

## Contributing

We welcome contributions! Please follow these guidelines:

1. **Fork & Branch**: `git checkout -b feature/your-feature`
2. **Code Style**: Python PEP 8, JavaScript ES6+
3. **Testing**: Add tests for new features
4. **Documentation**: Update README if adding new endpoints
5. **Pull Request**: Describe your changes and link any issues

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## Roadmap

### Near-term (v1.0)
- [ ] Multiplayer leaderboards & community rankings
- [ ] Mobile app (React Native)
- [ ] Video course integration (YouTube, Udemy)
- [ ] Study group collaboration tools

### Medium-term (v1.5)
- [ ] Spaced repetition flashcard deck export
- [ ] Integration with learning platforms (Coursera, Udacity)
- [ ] AI tutor for guided learning paths
- [ ] Certification program with proof-of-knowledge

### Long-term (v2.0)
- [ ] Blockchain-based credential verification
- [ ] Gamified AI/ML job matching
- [ ] Community-driven tech tree updates
- [ ] Advanced analytics dashboard

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Support

- **Issues & Bugs**: [GitHub Issues](https://github.com/nicobailon/AI-SOLO-LEVELING/issues)
- **Discussions**: [GitHub Discussions](https://github.com/nicobailon/AI-SOLO-LEVELING/discussions)
- **Documentation**: See `/docs` for detailed guides

---

## Credits

Inspired by the Solo Leveling manhwa series and the concept of systematic skill development.

Built with:
- [Claude API](https://anthropic.com) for AI/ML knowledge extraction
- [D3.js](https://d3js.org) for interactive visualizations
- [Flask](https://flask.palletsprojects.com) for web framework
- [Lucide Icons](https://lucide.dev) for beautiful icons

---

**ARISE!** Begin your journey to Shadow Monarch mastery today.
